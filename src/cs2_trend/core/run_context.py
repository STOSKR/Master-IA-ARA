"""Execution context and observability counters."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4


@dataclass
class RunContext:
    """Mutable context for a single extraction run."""

    run_id: str
    started_at_utc: datetime
    success_by_source: dict[str, int] = field(default_factory=dict)
    failure_by_source: dict[str, int] = field(default_factory=dict)

    @classmethod
    def create(cls) -> "RunContext":
        """Build a new run context with generated identifier and UTC timestamp."""

        return cls(run_id=uuid4().hex, started_at_utc=datetime.now(tz=UTC))

    def record_success(self, source: str) -> None:
        """Increment success counter for a given source."""

        self.success_by_source[source] = self.success_by_source.get(source, 0) + 1

    def record_failure(self, source: str) -> None:
        """Increment failure counter for a given source."""

        self.failure_by_source[source] = self.failure_by_source.get(source, 0) + 1
