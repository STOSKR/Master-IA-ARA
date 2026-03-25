"""Per-run observability models for source-level extraction metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TypedDict
from uuid import uuid4

from cs2_price_trend.quality.history_contract import normalize_source


class SourceMetricsPayload(TypedDict):
    """Serialized source-level observability counters."""

    success_count: int
    failure_count: int


class RunMetricsPayload(TypedDict):
    """Serialized run-level observability payload."""

    run_id: str
    started_at_utc: str
    total_success_count: int
    total_failure_count: int
    sources: dict[str, SourceMetricsPayload]


def _validate_non_negative_count(count: int) -> None:
    if count < 0:
        raise ValueError("Count must be non-negative")


@dataclass(slots=True)
class SourceRunMetrics:
    """Counters for one source during a run."""

    source: str
    success_count: int = 0
    failure_count: int = 0

    def record_success(self, count: int = 1) -> None:
        _validate_non_negative_count(count)
        self.success_count += count

    def record_failure(self, count: int = 1) -> None:
        _validate_non_negative_count(count)
        self.failure_count += count


@dataclass(slots=True)
class RunMetrics:
    """Run-level metrics containing per-source counters."""

    run_id: str
    started_at_utc: datetime = field(default_factory=lambda: datetime.now(UTC))
    per_source: dict[str, SourceRunMetrics] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.run_id = self.run_id.strip()
        if not self.run_id:
            raise ValueError("run_id must not be blank")
        if self.started_at_utc.tzinfo is None:
            self.started_at_utc = self.started_at_utc.replace(tzinfo=UTC)

    def _source_metrics(self, source: str) -> SourceRunMetrics:
        normalized_source: str = normalize_source(source)
        if normalized_source not in self.per_source:
            self.per_source[normalized_source] = SourceRunMetrics(source=normalized_source)
        return self.per_source[normalized_source]

    def record_success(self, source: str, count: int = 1) -> None:
        self._source_metrics(source).record_success(count)

    def record_failure(self, source: str, count: int = 1) -> None:
        self._source_metrics(source).record_failure(count)

    @property
    def total_success_count(self) -> int:
        return sum(metrics.success_count for metrics in self.per_source.values())

    @property
    def total_failure_count(self) -> int:
        return sum(metrics.failure_count for metrics in self.per_source.values())

    def as_observability_payload(self) -> RunMetricsPayload:
        return {
            "run_id": self.run_id,
            "started_at_utc": self.started_at_utc.isoformat(),
            "total_success_count": self.total_success_count,
            "total_failure_count": self.total_failure_count,
            "sources": {
                source: {
                    "success_count": metrics.success_count,
                    "failure_count": metrics.failure_count,
                }
                for source, metrics in sorted(self.per_source.items())
            },
        }

    def as_dict(self) -> RunMetricsPayload:
        """Backward-compatible alias for the observability payload."""

        return self.as_observability_payload()


def build_run_metrics(run_id: str | None = None) -> RunMetrics:
    """Create a RunMetrics object with a generated run_id when not provided."""

    resolved_run_id: str = run_id or f"run-{uuid4().hex[:12]}"
    return RunMetrics(run_id=resolved_run_id)
