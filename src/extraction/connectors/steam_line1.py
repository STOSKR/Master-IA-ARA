from __future__ import annotations

import json
import re
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from extraction.models import ExtractionTarget, PricePoint, ProbeSample

_LINE1_PATTERN = re.compile(r"var\s+line1\s*=\s*(\[[\s\S]*?\]);", re.MULTILINE)


def parse_steam_line1_points(
    *,
    sample: ProbeSample,
    target: ExtractionTarget,
) -> tuple[PricePoint, ...]:
    """Parse Steam listing inline ``line1`` history fallback into normalized points."""

    _ = target
    html = sample.body.decode("utf-8", errors="replace")
    match = _LINE1_PATTERN.search(html)
    if match is None:
        raise ValueError("inline line1 history not found")

    try:
        rows = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ValueError("invalid inline line1 JSON array") from exc

    if not isinstance(rows, Sequence) or not rows:
        raise ValueError("inline line1 array is empty")

    points: list[PricePoint] = []
    for row in rows:
        if not isinstance(row, Sequence) or len(row) < 3:
            continue

        timestamp = _parse_steam_line1_timestamp(row[0])
        price = _parse_float(row[1])
        volume = _parse_int(row[2])

        points.append(
            PricePoint(
                timestamp=timestamp,
                price=price,
                volume=volume,
                currency="USD",
            )
        )

    if not points:
        raise ValueError("inline line1 array does not contain valid datapoints")

    return tuple(points)


def _parse_steam_line1_timestamp(raw: Any) -> datetime:
    if not isinstance(raw, str):
        raise ValueError("line1 timestamp must be a string")

    normalized = raw.strip()
    if not normalized:
        raise ValueError("line1 timestamp is blank")

    prefix = normalized.split(" +", maxsplit=1)[0].strip()
    parsed = datetime.strptime(prefix, "%b %d %Y %H:")
    return parsed.replace(tzinfo=UTC)


def _parse_float(raw: Any) -> float:
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        cleaned = raw.strip().replace(",", "")
        return float(cleaned)
    raise ValueError("line1 numeric field cannot be parsed as float")


def _parse_int(raw: Any) -> int:
    return int(round(_parse_float(raw)))
