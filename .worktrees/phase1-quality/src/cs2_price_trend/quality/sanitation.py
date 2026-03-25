"""Utilities for duplicate detection and basic price outlier sanitation."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from .frame_utils import missing_columns, normalize_columns

DEFAULT_DUPLICATE_SUBSET: tuple[str, ...] = (
    "timestamp_utc",
    "source",
    "canonical_item_id",
    "currency",
    "price_basis",
)

DEFAULT_OUTLIER_GROUP_BY: tuple[str, ...] = (
    "source",
    "canonical_item_id",
    "currency",
    "price_basis",
)


def _validate_present_columns(
    frame: pd.DataFrame, columns: Sequence[str], *, context: str
) -> tuple[str, ...]:
    normalized: tuple[str, ...] = normalize_columns(columns)
    missing: tuple[str, ...] = missing_columns(frame, normalized)
    if missing:
        joined_missing: str = ", ".join(missing)
        raise KeyError(f"Missing {context} columns: {joined_missing}")
    return normalized


def _iter_groups(frame: pd.DataFrame, group_by: Sequence[str]) -> list[pd.DataFrame]:
    group_columns: tuple[str, ...] = normalize_columns(group_by, allow_empty=True)
    if not group_columns:
        return [frame]
    _validate_present_columns(frame, group_columns, context="group_by")
    grouped = frame.groupby(list(group_columns), dropna=False, sort=False)
    return [group for _, group in grouped]


def _iqr_bounds(series: pd.Series, whisker_width: float) -> tuple[float, float]:
    if whisker_width < 0:
        raise ValueError("whisker_width must be non-negative")
    q1: float = float(series.quantile(0.25))
    q3: float = float(series.quantile(0.75))
    iqr: float = q3 - q1
    lower_bound: float = q1 - whisker_width * iqr
    upper_bound: float = q3 + whisker_width * iqr
    return lower_bound, upper_bound


def find_duplicate_rows(
    frame: pd.DataFrame, subset: Sequence[str] = DEFAULT_DUPLICATE_SUBSET
) -> pd.DataFrame:
    """Return duplicated rows according to a configurable subset of columns."""

    subset_columns: tuple[str, ...] = _validate_present_columns(
        frame, subset, context="duplicate subset"
    )
    duplicate_mask: pd.Series = frame.duplicated(subset=list(subset_columns), keep=False)
    return frame.loc[duplicate_mask].copy()


def drop_duplicate_rows(
    frame: pd.DataFrame, subset: Sequence[str] = DEFAULT_DUPLICATE_SUBSET
) -> pd.DataFrame:
    """Drop duplicated rows and keep first occurrence by subset."""

    subset_columns: tuple[str, ...] = _validate_present_columns(
        frame, subset, context="duplicate subset"
    )
    return frame.drop_duplicates(subset=list(subset_columns), keep="first").reset_index(drop=True)


def detect_price_outliers_iqr(
    frame: pd.DataFrame,
    price_column: str = "price",
    group_by: Sequence[str] = DEFAULT_OUTLIER_GROUP_BY,
    whisker_width: float = 1.5,
) -> pd.Series:
    """Detect price outliers using IQR bounds per group."""

    _validate_present_columns(frame, (price_column,), context="price")

    if frame.empty:
        return pd.Series(False, index=frame.index, dtype=bool)

    outlier_mask: pd.Series = pd.Series(False, index=frame.index, dtype=bool)
    grouped_frames: list[pd.DataFrame] = _iter_groups(frame, group_by)

    for group in grouped_frames:
        lower_bound, upper_bound = _iqr_bounds(group[price_column], whisker_width)
        group_outliers: pd.Series = (group[price_column] < lower_bound) | (
            group[price_column] > upper_bound
        )
        outlier_mask.loc[group.index] = group_outliers.fillna(False)

    return outlier_mask


def sanitize_price_outliers_iqr(
    frame: pd.DataFrame,
    price_column: str = "price",
    group_by: Sequence[str] = DEFAULT_OUTLIER_GROUP_BY,
    whisker_width: float = 1.5,
) -> pd.DataFrame:
    """Clip price outliers to IQR lower/upper bounds per group."""

    _validate_present_columns(frame, (price_column,), context="price")

    sanitized: pd.DataFrame = frame.copy()
    grouped_frames: list[pd.DataFrame] = _iter_groups(sanitized, group_by)

    for group in grouped_frames:
        lower_bound, upper_bound = _iqr_bounds(group[price_column], whisker_width)
        sanitized.loc[group.index, price_column] = group[price_column].clip(
            lower=lower_bound, upper=upper_bound
        )

    return sanitized
