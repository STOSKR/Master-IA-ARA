from __future__ import annotations

import pandas as pd
import pytest

from cs2_price_trend.quality.sanitation import (
    detect_price_outliers_iqr,
    drop_duplicate_rows,
    find_duplicate_rows,
    sanitize_price_outliers_iqr,
)


def _duplicate_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp_utc": [
                "2026-03-25T00:00:00Z",
                "2026-03-25T00:00:00Z",
                "2026-03-25T01:00:00Z",
            ],
            "source": ["steam", "steam", "steam"],
            "canonical_item_id": ["ak_redline_ft", "ak_redline_ft", "ak_redline_ft"],
            "currency": ["USD", "USD", "USD"],
            "price_basis": ["listing", "listing", "listing"],
            "price": [10.0, 10.0, 10.3],
        }
    )


def _outlier_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "source": ["steam"] * 6,
            "canonical_item_id": ["awp_asiimov_bs"] * 6,
            "currency": ["USD"] * 6,
            "price_basis": ["listing"] * 6,
            "price": [10.0, 10.1, 10.2, 10.3, 10.4, 500.0],
        }
    )


def test_find_duplicate_rows_returns_all_duplicated_instances() -> None:
    duplicated: pd.DataFrame = find_duplicate_rows(_duplicate_frame())

    assert len(duplicated) == 2


def test_drop_duplicate_rows_keeps_first_occurrence() -> None:
    deduplicated: pd.DataFrame = drop_duplicate_rows(_duplicate_frame())

    assert len(deduplicated) == 2
    assert deduplicated.loc[0, "timestamp_utc"] == "2026-03-25T00:00:00Z"


def test_duplicate_detection_is_deterministic() -> None:
    frame: pd.DataFrame = _duplicate_frame()

    first_pass: pd.DataFrame = find_duplicate_rows(frame)
    second_pass: pd.DataFrame = find_duplicate_rows(frame)

    pd.testing.assert_frame_equal(first_pass, second_pass)


def test_detect_price_outliers_iqr_flags_outlier_value() -> None:
    frame: pd.DataFrame = _outlier_frame()

    outlier_mask: pd.Series = detect_price_outliers_iqr(frame)

    assert int(outlier_mask.sum()) == 1
    assert bool(outlier_mask.iloc[-1])


def test_sanitize_price_outliers_iqr_clips_extreme_value() -> None:
    frame: pd.DataFrame = _outlier_frame()

    sanitized: pd.DataFrame = sanitize_price_outliers_iqr(frame)

    assert float(sanitized["price"].iloc[-1]) < float(frame["price"].iloc[-1])
    assert float(sanitized["price"].max()) < 100.0


def test_detect_price_outliers_iqr_returns_empty_series_for_empty_frame() -> None:
    frame: pd.DataFrame = _outlier_frame().iloc[:0]

    outlier_mask: pd.Series = detect_price_outliers_iqr(frame)

    assert outlier_mask.empty
    assert outlier_mask.dtype == bool


def test_detect_price_outliers_iqr_requires_price_column() -> None:
    frame: pd.DataFrame = _outlier_frame().drop(columns=["price"])

    with pytest.raises(KeyError, match="Missing price columns"):
        detect_price_outliers_iqr(frame)


def test_sanitize_price_outliers_iqr_rejects_negative_whisker_width() -> None:
    with pytest.raises(ValueError, match="whisker_width must be non-negative"):
        sanitize_price_outliers_iqr(_outlier_frame(), whisker_width=-0.1)


def test_detect_price_outliers_iqr_applies_groupwise_bounds() -> None:
    frame: pd.DataFrame = pd.DataFrame(
        {
            "source": ["steam"] * 4 + ["csfloat"] * 4,
            "canonical_item_id": ["ak_redline_ft"] * 4 + ["m4a1_hyperbeast_mw"] * 4,
            "currency": ["USD"] * 8,
            "price_basis": ["listing"] * 8,
            "price": [10.0, 10.0, 10.1, 100.0, 500.0, 500.0, 500.0, 5.0],
        }
    )

    outlier_mask: pd.Series = detect_price_outliers_iqr(frame)

    assert int(outlier_mask.sum()) == 2
    assert bool(outlier_mask.iloc[3])
    assert bool(outlier_mask.iloc[7])


def test_sanitize_price_outliers_iqr_uses_groupwise_bounds() -> None:
    frame: pd.DataFrame = pd.DataFrame(
        {
            "source": ["steam"] * 4 + ["csfloat"] * 4,
            "canonical_item_id": ["ak_redline_ft"] * 4 + ["m4a1_hyperbeast_mw"] * 4,
            "currency": ["USD"] * 8,
            "price_basis": ["listing"] * 8,
            "price": [10.0, 10.0, 10.1, 100.0, 500.0, 500.0, 500.0, 5.0],
        }
    )

    sanitized: pd.DataFrame = sanitize_price_outliers_iqr(frame)

    assert float(sanitized.loc[3, "price"]) < float(frame.loc[3, "price"])
    assert float(sanitized.loc[7, "price"]) > float(frame.loc[7, "price"])


def test_sanitize_price_outliers_iqr_does_not_mutate_input_frame() -> None:
    frame: pd.DataFrame = _outlier_frame()
    original: pd.DataFrame = frame.copy(deep=True)

    sanitize_price_outliers_iqr(frame)

    pd.testing.assert_frame_equal(frame, original)
