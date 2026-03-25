"""Typed models for probe and catalog phase services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from cs2_trend.domain.models import CanonicalItem

type JsonPrimitive = str | int | float | bool | None
type JsonValue = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]
type CatalogOutputFormat = Literal["json", "csv", "both"]


@dataclass(frozen=True)
class HttpJsonResponse:
    """Structured HTTP response after JSON decoding."""

    endpoint: str
    status_code: int
    payload: JsonValue


@dataclass(frozen=True)
class ProbeRecord:
    """Metadata for one probe capture persisted to disk."""

    source: str
    endpoint: str
    status_code: int
    captured_at_utc: datetime
    dump_path: Path
    payload: JsonValue


@dataclass(frozen=True)
class CatalogPersistenceResult:
    """Result of writing canonical catalog records to tabular files."""

    records: tuple[CanonicalItem, ...]
    json_path: Path | None
    csv_path: Path | None