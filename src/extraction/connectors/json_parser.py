from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from extraction.errors import UnknownResponseShapeError
from extraction.models import ExtractionTarget, PricePoint, ProbeSample

TimestampUnit = Literal["seconds", "milliseconds", "iso", "auto"]


@dataclass(slots=True, frozen=True)
class JsonShapeSpec:
    """Declarative JSON shape specification for connector parsing."""

    points_path: tuple[str, ...]
    timestamp_field: str
    price_field: str
    volume_field: str | None = None
    currency_field: str | None = None
    timestamp_unit: TimestampUnit = "auto"


def build_json_point_parser(
    *,
    source_name: str,
    shapes: Sequence[JsonShapeSpec],
    default_currency: str = "USD",
) -> Callable[[ProbeSample, ExtractionTarget], tuple[PricePoint, ...]]:
    """Build a strict parser callable that supports only declared JSON shapes."""

    def _parse(sample: ProbeSample, target: ExtractionTarget) -> tuple[PricePoint, ...]:
        payload = _decode_json(sample=sample, source_name=source_name)
        attempted_paths: list[str] = []

        for shape in shapes:
            attempted_paths.append(".".join(shape.points_path) or "<root>")
            rows = _resolve_points(payload=payload, path=shape.points_path)
            if rows is None:
                continue

            try:
                parsed_points = _parse_rows(
                    rows=rows,
                    shape=shape,
                    default_currency=_resolve_default_currency(target, default_currency),
                )
            except ValueError:
                continue

            if parsed_points:
                return parsed_points

        raise UnknownResponseShapeError(
            source_name=source_name,
            sample=sample,
            detail=(
                "response does not match any supported JSON shape "
                f"for paths={attempted_paths}"
            ),
        )

    return _parse


def _decode_json(*, sample: ProbeSample, source_name: str) -> Any:
    try:
        return json.loads(sample.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UnknownResponseShapeError(
            source_name=source_name,
            sample=sample,
            detail=f"invalid JSON payload ({type(exc).__name__})",
        ) from exc


def _resolve_points(*, payload: Any, path: tuple[str, ...]) -> list[Mapping[str, Any]] | None:
    current: Any = payload
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)

    if not isinstance(current, list) or not current:
        return None

    normalized: list[Mapping[str, Any]] = []
    for row in current:
        if not isinstance(row, Mapping):
            return None
        normalized.append(row)
    return normalized


def _parse_rows(
    *,
    rows: Sequence[Mapping[str, Any]],
    shape: JsonShapeSpec,
    default_currency: str,
) -> tuple[PricePoint, ...]:
    points: list[PricePoint] = []
    for row in rows:
        if shape.timestamp_field not in row or shape.price_field not in row:
            raise ValueError("missing required fields")

        timestamp = _parse_timestamp(row[shape.timestamp_field], shape.timestamp_unit)
        price = _parse_price(row[shape.price_field])

        volume: int | None = None
        if shape.volume_field is not None and row.get(shape.volume_field) is not None:
            volume = _parse_volume(row[shape.volume_field])

        currency = default_currency
        if shape.currency_field is not None and isinstance(row.get(shape.currency_field), str):
            currency = row[shape.currency_field].strip().upper()

        points.append(
            PricePoint(
                timestamp=timestamp,
                price=price,
                volume=volume,
                currency=currency,
            )
        )

    return tuple(points)


def _parse_timestamp(value: Any, unit: TimestampUnit) -> datetime:
    if isinstance(value, str):
        candidate = value.strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(candidate)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    if isinstance(value, (int, float)):
        numeric = float(value)
        if unit == "milliseconds":
            numeric /= 1000.0
        elif unit == "auto" and numeric > 1_000_000_000_000:
            numeric /= 1000.0
        return datetime.fromtimestamp(numeric, tz=UTC)

    raise ValueError("unsupported timestamp type")


def _parse_price(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        normalized = value.strip().replace(",", "")
        normalized = re.sub(r"[^0-9.\-]", "", normalized)
        if not normalized:
            raise ValueError("empty normalized price")
        return float(normalized)

    raise ValueError("unsupported price type")


def _parse_volume(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip().replace(",", "")
        if not stripped:
            raise ValueError("empty volume")
        return int(float(stripped))
    raise ValueError("unsupported volume type")


def _resolve_default_currency(target: ExtractionTarget, fallback: str) -> str:
    context_currency = target.context.get("currency")
    if isinstance(context_currency, str) and context_currency.strip():
        return context_currency.strip().upper()
    return fallback