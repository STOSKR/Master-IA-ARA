"""Protocols for Phase 0 services and repositories."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from cs2_trend.domain.models import CanonicalItem
from cs2_trend.phase0.models import (
    CatalogOutputFormat,
    CatalogPersistenceResult,
    HttpJsonResponse,
    JsonValue,
    ProbeRecord,
)


class JsonHttpClient(Protocol):
    """Abstract async HTTP client returning decoded JSON payloads."""

    async def fetch_json(self, *, endpoint: str) -> HttpJsonResponse:
        """Request an endpoint and decode its JSON response."""


class ProbeDumpStore(Protocol):
    """Storage contract for timestamped probe dumps."""

    def write_probe_dump(
        self,
        *,
        source: str,
        endpoint: str,
        run_id: str,
        status_code: int,
        payload: JsonValue,
    ) -> ProbeRecord:
        """Persist payload and return metadata for the generated dump."""

    def read_probe_payload(self, *, path: Path) -> JsonValue:
        """Load and return probe payload from one dump file."""

    def latest_probe_path(self, *, source: str) -> Path | None:
        """Return most recent dump for source, if available."""


class CatalogParser(Protocol):
    """Parses source payload into canonical item records."""

    def parse_catalog_items(self, *, payload: JsonValue) -> tuple[CanonicalItem, ...]:
        """Parse JSON payload into canonical catalog records."""


class CatalogStore(Protocol):
    """Persists canonical item records in tabular outputs."""

    def persist_catalog(
        self,
        *,
        records: tuple[CanonicalItem, ...],
        output_format: CatalogOutputFormat,
        base_name: str,
    ) -> CatalogPersistenceResult:
        """Persist records as JSON, CSV, or both."""