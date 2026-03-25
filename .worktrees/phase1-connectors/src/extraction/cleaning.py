from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import replace
from datetime import UTC

from extraction.models import PricePoint


def clean_price_points(points: Iterable[PricePoint]) -> tuple[PricePoint, ...]:
    """Apply initial anomaly filtering and deterministic ordering for extracted points."""

    normalized: list[PricePoint] = []
    for point in points:
        if not math.isfinite(point.price) or point.price <= 0:
            continue

        fixed_timestamp = point.timestamp
        if fixed_timestamp.tzinfo is None:
            fixed_timestamp = fixed_timestamp.replace(tzinfo=UTC)

        normalized.append(
            replace(
                point,
                timestamp=fixed_timestamp,
                currency=point.currency.strip().upper(),
            )
        )

    normalized.sort(key=lambda value: value.timestamp)
    return tuple(normalized)
