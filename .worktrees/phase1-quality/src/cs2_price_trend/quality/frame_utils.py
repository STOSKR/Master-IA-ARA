"""Shared dataframe helpers for quality modules."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd


def normalize_columns(columns: Sequence[str], *, allow_empty: bool = False) -> tuple[str, ...]:
    """Return deduplicated column names preserving original order."""

    normalized: tuple[str, ...] = tuple(dict.fromkeys(columns))
    if not normalized and not allow_empty:
        raise ValueError("Expected at least one column name")
    for column in normalized:
        if not column.strip():
            raise ValueError("Column names must not be blank")
    return normalized


def missing_columns(frame: pd.DataFrame, expected_columns: Sequence[str]) -> tuple[str, ...]:
    """Return missing columns from expected_columns in deterministic order."""

    expected: tuple[str, ...] = normalize_columns(expected_columns)
    return tuple(column for column in expected if column not in frame.columns)
