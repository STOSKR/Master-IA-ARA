"""Canonical row contract for unified historical market data."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, NotRequired, TypedDict

ALLOWED_SOURCES: tuple[str, ...] = (
    "steam",
    "steamdt",
    "buff163",
    "csmoney",
    "csfloat",
)

CURRENCY_CODE_REGEX: str = r"^[A-Z]{3}$"

PRICE_BASIS_ALLOWED: tuple[str, ...] = (
    "listing",
    "sale",
)

HISTORY_MANDATORY_FIELDS: tuple[str, ...] = (
    "timestamp_utc",
    "source",
    "canonical_item_id",
    "price",
    "currency",
    "price_basis",
)

HISTORY_OPTIONAL_FIELDS: tuple[str, ...] = (
    "volume",
    "availability",
)

HISTORY_ALL_FIELDS: tuple[str, ...] = HISTORY_MANDATORY_FIELDS + HISTORY_OPTIONAL_FIELDS

CanonicalSource = Literal["steam", "steamdt", "buff163", "csmoney", "csfloat"]

_ALLOWED_SOURCE_SET: frozenset[str] = frozenset(ALLOWED_SOURCES)


def normalize_source(source: str) -> str:
    """Normalize and validate a source name against canonical allowed sources."""

    normalized: str = source.strip().lower()
    if not normalized:
        raise ValueError("source must not be blank")
    if normalized not in _ALLOWED_SOURCE_SET:
        raise ValueError(f"Unknown source: {source}")
    return normalized


class CanonicalHistoryRow(TypedDict):
    """Canonical contract for one historical datapoint across all sources."""

    timestamp_utc: datetime
    source: CanonicalSource
    canonical_item_id: str
    price: float
    currency: str
    price_basis: str
    volume: NotRequired[float | None]
    availability: NotRequired[float | None]
