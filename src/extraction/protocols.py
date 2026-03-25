from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from extraction.models import ConnectorExtraction, ExtractionTarget, ProbeSample


@dataclass(slots=True, frozen=True)
class HttpResponse:
    """Typed HTTP response envelope used by connectors."""

    url: str
    status_code: int
    headers: Mapping[str, str]
    body: bytes


class AsyncHttpClient(Protocol):
    """Minimal asynchronous HTTP client contract for connectors."""

    async def get(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> HttpResponse:
        ...

    async def aclose(self) -> None:
        ...


class MarketConnector(Protocol):
    """Connector protocol for probe-first data extraction."""

    source_name: str

    async def probe(self, target: ExtractionTarget) -> ProbeSample:
        ...

    async def extract(self, target: ExtractionTarget) -> ConnectorExtraction:
        ...
