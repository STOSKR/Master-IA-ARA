"""Transform extraction outputs into unified historical dataframes."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC
from typing import Any

import pandas as pd

from cs2_price_trend.quality.history_contract import HISTORY_ALL_FIELDS
from extraction.models import ExtractionRunResult


def extraction_results_to_history_frame(
    results: Sequence[ExtractionRunResult],
    *,
    price_basis: str = "listing",
) -> pd.DataFrame:
    """Convert kernel run results into the canonical historical table contract."""

    rows: list[dict[str, Any]] = []

    for result in results:
        if not result.success or result.extraction is None:
            continue

        canonical_item_id = _resolve_canonical_item_id(result)
        for point in result.extraction.points:
            rows.append(
                {
                    "timestamp_utc": point.timestamp.astimezone(UTC),
                    "source": result.source_name,
                    "canonical_item_id": canonical_item_id,
                    "price": float(point.price),
                    "currency": point.currency,
                    "price_basis": price_basis,
                    "volume": float(point.volume) if point.volume is not None else None,
                    "availability": None,
                }
            )

    if not rows:
        return pd.DataFrame(columns=list(HISTORY_ALL_FIELDS))

    frame = pd.DataFrame(rows, columns=list(HISTORY_ALL_FIELDS))
    return frame.sort_values(
        by=["timestamp_utc", "source", "canonical_item_id"],
        kind="stable",
    ).reset_index(drop=True)


def _resolve_canonical_item_id(result: ExtractionRunResult) -> str:
    context_value = result.target.context.get("canonical_item_id")
    if isinstance(context_value, str):
        normalized = context_value.strip()
        if normalized:
            return normalized
    return str(result.target.item_id)
