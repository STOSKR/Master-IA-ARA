from __future__ import annotations

import pandas as pd
import pandera.pandas as pa
import pytest

from cs2_price_trend.quality.validation import validate_history_dataframe


def _valid_history_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp_utc": ["2026-03-25T00:00:00Z", "2026-03-25T01:00:00Z"],
            "source": ["steam", "csfloat"],
            "canonical_item_id": ["ak_redline_ft", "m4a1_hyperbeast_mw"],
            "price": [12.45, 24.10],
            "currency": ["USD", "USD"],
            "price_basis": ["listing", "listing"],
            "volume": [15, 3],
        }
    )


def test_validate_history_dataframe_accepts_valid_frame() -> None:
    frame: pd.DataFrame = _valid_history_frame()

    validated: pd.DataFrame = validate_history_dataframe(frame)

    assert len(validated) == 2
    assert "availability" not in validated.columns


def test_validate_history_dataframe_rejects_missing_required_column() -> None:
    frame: pd.DataFrame = _valid_history_frame().drop(columns=["price_basis"])

    with pytest.raises(ValueError, match="Missing required columns"):
        validate_history_dataframe(frame)


def test_validate_history_dataframe_rejects_invalid_currency_code() -> None:
    frame: pd.DataFrame = _valid_history_frame()
    frame.loc[0, "currency"] = "usd"

    with pytest.raises(pa.errors.SchemaError):
        validate_history_dataframe(frame)


def test_validate_history_dataframe_rejects_unknown_source() -> None:
    frame: pd.DataFrame = _valid_history_frame()
    frame.loc[0, "source"] = "unknown_market"

    with pytest.raises(pa.errors.SchemaError):
        validate_history_dataframe(frame)


def test_validate_history_dataframe_rejects_unknown_price_basis() -> None:
    frame: pd.DataFrame = _valid_history_frame()
    frame.loc[0, "price_basis"] = "midpoint"

    with pytest.raises(pa.errors.SchemaError):
        validate_history_dataframe(frame)


def test_validate_history_dataframe_accepts_empty_frame_with_required_columns() -> None:
    frame: pd.DataFrame = _valid_history_frame().iloc[:0]

    validated: pd.DataFrame = validate_history_dataframe(frame)

    assert validated.empty


def test_validate_history_dataframe_reports_all_missing_columns_in_order() -> None:
    frame: pd.DataFrame = _valid_history_frame().drop(columns=["price", "price_basis"])

    with pytest.raises(ValueError, match="Missing required columns: price, price_basis"):
        validate_history_dataframe(frame)


def test_validate_history_dataframe_lazy_mode_raises_schema_errors() -> None:
    frame: pd.DataFrame = _valid_history_frame()
    frame.loc[0, "source"] = "invalid"
    frame.loc[0, "currency"] = "usd"

    with pytest.raises(pa.errors.SchemaErrors):
        validate_history_dataframe(frame, lazy=True)
