"""Pandera schemas and validators for historical canonical tables."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd
import pandera.pandas as pa

from .frame_utils import missing_columns
from .history_contract import (
    ALLOWED_SOURCES,
    CURRENCY_CODE_REGEX,
    HISTORY_MANDATORY_FIELDS,
    PRICE_BASIS_ALLOWED,
)


def _non_blank(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().ne("")


HISTORY_SCHEMA: pa.DataFrameSchema = pa.DataFrameSchema(
    {
        "timestamp_utc": pa.Column(pa.DateTime, nullable=False, coerce=True),
        "source": pa.Column(
            pa.String,
            checks=[pa.Check.isin(ALLOWED_SOURCES), pa.Check(_non_blank)],
            nullable=False,
            coerce=True,
        ),
        "canonical_item_id": pa.Column(
            pa.String, checks=pa.Check(_non_blank), nullable=False, coerce=True
        ),
        "price": pa.Column(float, checks=pa.Check.ge(0.0), nullable=False, coerce=True),
        "currency": pa.Column(
            pa.String,
            checks=[pa.Check.str_matches(CURRENCY_CODE_REGEX)],
            nullable=False,
            coerce=True,
        ),
        "price_basis": pa.Column(
            pa.String,
            checks=[pa.Check(_non_blank), pa.Check.isin(PRICE_BASIS_ALLOWED)],
            nullable=False,
            coerce=True,
        ),
        "volume": pa.Column(
            float, checks=pa.Check.ge(0.0), nullable=True, required=False, coerce=True
        ),
        "availability": pa.Column(
            float, checks=pa.Check.ge(0.0), nullable=True, required=False, coerce=True
        ),
    },
    coerce=True,
    strict=False,
)


def ensure_required_columns(
    frame: pd.DataFrame, required: Sequence[str] = HISTORY_MANDATORY_FIELDS
) -> None:
    """Ensure a dataframe has all required canonical history columns."""

    missing: tuple[str, ...] = missing_columns(frame, required)
    if missing:
        joined_missing: str = ", ".join(missing)
        raise ValueError(f"Missing required columns: {joined_missing}")


def validate_history_dataframe(frame: pd.DataFrame, lazy: bool = False) -> pd.DataFrame:
    """Validate and coerce a canonical historical dataframe using Pandera."""

    ensure_required_columns(frame)
    return HISTORY_SCHEMA.validate(frame, lazy=lazy)
