from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from extraction.models import ExtractionTarget, PricePoint, ProbeSample


def parse_steam_pricehistory_points(
    *,
    sample: ProbeSample,
    target: ExtractionTarget,
) -> tuple[PricePoint, ...]:
    """Parse Steam ``/market/pricehistory`` payload into normalized points."""

    payload = _decode_pricehistory_payload(sample)
    prices = payload.get("prices")
    if not isinstance(prices, Sequence) or not prices:
        raise ValueError("steam pricehistory payload does not contain prices")

    currency = _resolve_currency(target)
    points: list[PricePoint] = []
    for row in prices:
        if not isinstance(row, Sequence) or isinstance(row, (str, bytes)) or len(row) < 2:
            continue

        timestamp = _parse_steam_timestamp(row[0])
        price = _parse_price(row[1])
        volume = _parse_volume(row[2]) if len(row) >= 3 else None

        points.append(
            PricePoint(
                timestamp=timestamp,
                price=price,
                volume=volume,
                currency=currency,
            )
        )

    if not points:
        raise ValueError("steam pricehistory payload does not contain valid points")

    return tuple(points)


def _decode_pricehistory_payload(sample: ProbeSample) -> Mapping[str, Any]:
    try:
        payload = json.loads(sample.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("steam pricehistory payload is not valid JSON") from exc

    if not isinstance(payload, Mapping):
        raise ValueError("steam pricehistory payload is not an object")

    if payload.get("success") is False:
        raise ValueError("steam pricehistory payload returned success=false")

    return payload


def _resolve_currency(target: ExtractionTarget) -> str:
    context_currency = target.context.get("currency")
    if isinstance(context_currency, str) and context_currency.strip():
        return context_currency.strip().upper()
    return "USD"


def _parse_steam_timestamp(raw: Any) -> datetime:
    if not isinstance(raw, str):
        raise ValueError("steam timestamp must be string")

    normalized = raw.strip()
    if not normalized:
        raise ValueError("steam timestamp cannot be blank")

    prefix = normalized.split(" +", maxsplit=1)[0].strip()
    parsed = datetime.strptime(prefix, "%b %d %Y %H:")
    return parsed.replace(tzinfo=UTC)


def _parse_price(raw: Any) -> float:
    if isinstance(raw, (int, float)):
        return float(raw)

    if isinstance(raw, str):
        cleaned = raw.replace("\u00a0", "").replace(" ", "").strip()
        cleaned = re.sub(r"[^0-9,.-]", "", cleaned)
        if not cleaned:
            raise ValueError("steam price cannot be empty")

        if "," in cleaned and "." not in cleaned:
            cleaned = cleaned.replace(",", ".")
        elif "," in cleaned and "." in cleaned:
            if cleaned.rfind(",") > cleaned.rfind("."):
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")

        return float(cleaned)

    raise ValueError("steam price has unsupported type")


def _parse_volume(raw: Any) -> int | None:
    if raw is None:
        return None

    if isinstance(raw, int):
        return raw

    if isinstance(raw, float):
        return int(round(raw))

    if isinstance(raw, str):
        cleaned = raw.replace(",", "").strip()
        if not cleaned:
            return None
        return int(round(float(cleaned)))

    raise ValueError("steam volume has unsupported type")