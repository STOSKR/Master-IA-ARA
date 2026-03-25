from __future__ import annotations

import pytest

from cs2_price_trend.reliability.run_metrics import build_run_metrics


def test_run_metrics_aggregates_counts_by_source() -> None:
    metrics = build_run_metrics("run-test-001")

    metrics.record_success("steam", count=2)
    metrics.record_failure("steam", count=1)
    metrics.record_success("csfloat", count=3)

    payload = metrics.as_dict()

    assert payload["run_id"] == "run-test-001"
    assert payload["total_success_count"] == 5
    assert payload["total_failure_count"] == 1
    assert payload["sources"]["steam"]["success_count"] == 2
    assert payload["sources"]["steam"]["failure_count"] == 1


def test_build_run_metrics_generates_run_id_when_missing() -> None:
    metrics = build_run_metrics()

    payload = metrics.as_observability_payload()

    assert payload["run_id"].startswith("run-")
    assert payload["started_at_utc"]


def test_run_metrics_reject_negative_counts() -> None:
    metrics = build_run_metrics("run-test-002")

    with pytest.raises(ValueError, match="Count must be non-negative"):
        metrics.record_success("steam", count=-1)


def test_run_metrics_reject_unknown_source() -> None:
    metrics = build_run_metrics("run-test-003")

    with pytest.raises(ValueError, match="Unknown source"):
        metrics.record_failure("unknown_source", count=1)


def test_run_metrics_normalizes_source_names() -> None:
    metrics = build_run_metrics("run-test-004")

    metrics.record_success(" Steam ", count=1)

    payload = metrics.as_observability_payload()
    assert payload["sources"]["steam"]["success_count"] == 1


def test_run_metrics_serialization_sorts_sources_deterministically() -> None:
    metrics = build_run_metrics("run-test-005")

    metrics.record_success("steamdt", count=1)
    metrics.record_success("buff163", count=1)
    metrics.record_success("csfloat", count=1)

    payload = metrics.as_observability_payload()

    assert list(payload["sources"].keys()) == ["buff163", "csfloat", "steamdt"]


def test_run_metrics_reject_blank_source() -> None:
    metrics = build_run_metrics("run-test-006")

    with pytest.raises(ValueError, match="source must not be blank"):
        metrics.record_failure("   ")
