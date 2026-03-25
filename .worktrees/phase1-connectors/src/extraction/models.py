from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True, frozen=True)
class ExtractionTarget:
    """Input target descriptor for one digital item extraction run."""

    item_id: str
    market_hash_name: str
    context: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class ProbeSample:
    """Raw sample captured from a source endpoint before parsing."""

    source_name: str
    url: str
    status_code: int
    headers: Mapping[str, str]
    body: bytes
    captured_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


@dataclass(slots=True, frozen=True)
class PricePoint:
    """Normalized temporal point for one observed market price."""

    timestamp: datetime
    price: float
    volume: int | None
    currency: str


@dataclass(slots=True, frozen=True)
class ConnectorExtraction:
    """Parsed connector output plus the probe sample used for traceability."""

    source_name: str
    target: ExtractionTarget
    sample: ProbeSample
    points: tuple[PricePoint, ...]


@dataclass(slots=True, frozen=True)
class ExtractionRunResult:
    """Per-connector result with observability fields."""

    source_name: str
    target: ExtractionTarget
    success: bool
    attempts: int
    started_at: datetime
    finished_at: datetime
    duration_seconds: float
    extraction: ConnectorExtraction | None = None
    error_type: str | None = None
    error_message: str | None = None
    dump_path: str | None = None


@dataclass(slots=True, frozen=True)
class ExtractionRunMetrics:
    """Run-level observability metrics for one kernel execution."""

    run_id: str
    started_at: datetime
    finished_at: datetime
    duration_seconds: float
    total_jobs: int
    success_count: int
    failure_count: int


@dataclass(slots=True, frozen=True)
class ExtractionRun:
    """Aggregate output from one kernel run."""

    metrics: ExtractionRunMetrics
    results: tuple[ExtractionRunResult, ...]
