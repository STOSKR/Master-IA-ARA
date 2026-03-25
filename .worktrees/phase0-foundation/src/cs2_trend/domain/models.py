"""Core domain models used across catalog and extraction phases."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

MarketSource = Literal["steam", "steamdt", "buff163", "csmoney", "csfloat"]


class CanonicalItem(BaseModel):
    """Normalized representation of a CS2 item across all market sources."""

    canonical_item_id: str = Field(min_length=3)
    weapon: str = Field(min_length=1)
    skin_name: str = Field(min_length=1)
    wear: str | None = None
    is_stattrak: bool = False
    is_souvenir: bool = False
    rarity: str | None = None
    collection: str | None = None
    source_keys: dict[MarketSource, str] = Field(default_factory=dict)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    @field_validator("canonical_item_id")
    @classmethod
    def canonical_id_must_not_have_spaces(cls, value: str) -> str:
        """Protect canonical identifiers from whitespace-only formatting."""

        normalized = value.strip()
        if not normalized or any(char.isspace() for char in normalized):
            raise ValueError("canonical_item_id must be non-empty and contain no whitespace")
        return normalized


class HistoricalPriceRow(BaseModel):
    """Unified row contract for extracted historical market prices."""

    timestamp_utc: datetime
    source: MarketSource
    canonical_item_id: str = Field(min_length=3)
    price: Decimal = Field(gt=Decimal("0"))
    currency: str = Field(min_length=3, max_length=3)
    price_basis: str = Field(min_length=1)
    volume: int | None = Field(default=None, ge=0)
    availability: int | None = Field(default=None, ge=0)

    @field_validator("timestamp_utc")
    @classmethod
    def timestamp_must_be_timezone_aware(cls, value: datetime) -> datetime:
        """Ensure historical records remain unambiguous across regions."""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp_utc must include timezone information")
        return value

    @field_validator("currency")
    @classmethod
    def currency_must_be_uppercase(cls, value: str) -> str:
        """Normalize ISO-like currency codes to uppercase."""

        return value.upper()
