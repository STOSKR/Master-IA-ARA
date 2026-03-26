from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from cs2_price_trend.quality.history_contract import HISTORY_ALL_FIELDS
from cs2_price_trend.quality.transforms import extraction_results_to_history_frame
from extraction.models import (
    ConnectorExtraction,
    ExtractionRunResult,
    ExtractionTarget,
    PricePoint,
    ProbeSample,
)


def test_extraction_results_to_history_frame_maps_success_rows() -> None:
    target = ExtractionTarget(
        item_id="item-1",
        market_hash_name="AK-47 | Redline",
        context={"canonical_item_id": "ak_47__redline__field_tested"},
    )
    sample = ProbeSample(
        source_name="steam",
        url="https://example.test/history",
        status_code=200,
        headers={},
        body=b"{}",
    )
    extraction = ConnectorExtraction(
        source_name="steam",
        target=target,
        sample=sample,
        points=(
            PricePoint(
                timestamp=datetime(2026, 3, 25, 0, 0, tzinfo=UTC),
                price=10.5,
                volume=3,
                currency="usd",
            ),
        ),
    )

    success_result = ExtractionRunResult(
        source_name="steam",
        target=target,
        success=True,
        attempts=1,
        started_at=datetime(2026, 3, 25, 0, 0, tzinfo=UTC),
        finished_at=datetime(2026, 3, 25, 0, 0, tzinfo=UTC),
        duration_seconds=0.1,
        extraction=extraction,
    )
    failed_result = ExtractionRunResult(
        source_name="steam",
        target=target,
        success=False,
        attempts=3,
        started_at=datetime(2026, 3, 25, 0, 0, tzinfo=UTC),
        finished_at=datetime(2026, 3, 25, 0, 0, tzinfo=UTC),
        duration_seconds=0.3,
        error_type="RuntimeError",
        error_message="boom",
    )

    frame = extraction_results_to_history_frame([success_result, failed_result])

    assert list(frame.columns) == list(HISTORY_ALL_FIELDS)
    assert len(frame) == 1
    assert frame.loc[0, "source"] == "steam"
    assert frame.loc[0, "canonical_item_id"] == "ak_47__redline__field_tested"
    assert float(frame.loc[0, "price"]) == 10.5
    assert float(frame.loc[0, "volume"]) == 3.0


def test_extraction_results_to_history_frame_returns_empty_schema_when_no_success() -> (
    None
):
    frame = extraction_results_to_history_frame([])

    assert isinstance(frame, pd.DataFrame)
    assert frame.empty
    assert list(frame.columns) == list(HISTORY_ALL_FIELDS)


def test_extraction_results_to_history_frame_includes_context_columns_when_requested() -> (
    None
):
    target = ExtractionTarget(
        item_id="item-2",
        market_hash_name="AWP | Neo-Noir",
        context={
            "canonical_item_id": "awp__neo_noir",
            "object_type": "weapon",
            "object_subtype": "rifle",
            "type_name": "Weapon",
        },
    )
    sample = ProbeSample(
        source_name="steam",
        url="https://example.test/history",
        status_code=200,
        headers={},
        body=b"{}",
    )
    extraction = ConnectorExtraction(
        source_name="steam",
        target=target,
        sample=sample,
        points=(
            PricePoint(
                timestamp=datetime(2026, 3, 25, 0, 0, tzinfo=UTC),
                price=10.5,
                volume=3,
                currency="usd",
            ),
        ),
    )
    success_result = ExtractionRunResult(
        source_name="steam",
        target=target,
        success=True,
        attempts=1,
        started_at=datetime(2026, 3, 25, 0, 0, tzinfo=UTC),
        finished_at=datetime(2026, 3, 25, 0, 0, tzinfo=UTC),
        duration_seconds=0.1,
        extraction=extraction,
    )

    frame = extraction_results_to_history_frame(
        [success_result],
        include_context_columns=True,
    )

    assert "object_type" in frame.columns
    assert "object_subtype" in frame.columns
    assert "type_name" in frame.columns
    assert frame.loc[0, "object_type"] == "weapon"
