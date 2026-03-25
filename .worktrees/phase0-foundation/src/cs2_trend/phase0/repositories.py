"""File-backed repository implementations for phase 0 services."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import cast

from cs2_trend.core.pathing import sanitize_component
from cs2_trend.core.time import format_utc_filename_timestamp, utc_now
from cs2_trend.domain.models import CanonicalItem
from cs2_trend.phase0.interfaces import CatalogStore, ProbeDumpStore
from cs2_trend.phase0.models import (
    CatalogOutputFormat,
    CatalogPersistenceResult,
    JsonValue,
    ProbeRecord,
)


def _dump_json_pretty(payload: JsonValue) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _dump_json_compact(payload: JsonValue) -> str:
    return json.dumps(payload, ensure_ascii=False)


class FileProbeDumpRepository(ProbeDumpStore):
    """Persists and loads timestamped probe dumps on local filesystem."""

    def __init__(self, *, base_dir: Path) -> None:
        self._base_dir = base_dir

    def write_probe_dump(
        self,
        *,
        source: str,
        endpoint: str,
        run_id: str,
        status_code: int,
        payload: JsonValue,
    ) -> ProbeRecord:
        captured_at_utc = utc_now()
        timestamp = format_utc_filename_timestamp(captured_at_utc)
        source_part = sanitize_component(source)
        endpoint_part = sanitize_component(endpoint)
        file_name = f"{timestamp}_{run_id}_{source_part}_{endpoint_part}_{status_code}.json"

        self._base_dir.mkdir(parents=True, exist_ok=True)
        dump_path = self._base_dir / file_name
        raw_payload = {
            "captured_at_utc": captured_at_utc.isoformat(),
            "source": source,
            "endpoint": endpoint,
            "status_code": status_code,
            "payload": payload,
        }
        serialized = _dump_json_pretty(cast(JsonValue, raw_payload))
        dump_path.write_text(serialized, encoding="utf-8")

        return ProbeRecord(
            source=source,
            endpoint=endpoint,
            status_code=status_code,
            captured_at_utc=captured_at_utc,
            dump_path=dump_path,
            payload=payload,
        )

    def read_probe_payload(self, *, path: Path) -> JsonValue:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and "payload" in raw:
            payload = cast(JsonValue, raw["payload"])
        else:
            payload = cast(JsonValue, raw)
        return payload

    def latest_probe_path(self, *, source: str) -> Path | None:
        source_part = sanitize_component(source)
        pattern = f"*_{source_part}_*.json"
        candidates = sorted(self._base_dir.glob(pattern), reverse=True)
        if not candidates:
            return None
        return candidates[0]


class FileCatalogRepository(CatalogStore):
    """Persists canonical item records as JSON and CSV tabular artifacts."""

    _CSV_HEADERS: tuple[str, ...] = (
        "canonical_item_id",
        "weapon",
        "skin_name",
        "wear",
        "is_stattrak",
        "is_souvenir",
        "rarity",
        "collection",
        "source_keys",
        "metadata",
    )

    def __init__(self, *, base_dir: Path) -> None:
        self._base_dir = base_dir

    def persist_catalog(
        self,
        *,
        records: tuple[CanonicalItem, ...],
        output_format: CatalogOutputFormat,
        base_name: str,
    ) -> CatalogPersistenceResult:
        self._base_dir.mkdir(parents=True, exist_ok=True)
        sanitized_name = sanitize_component(base_name)

        json_path: Path | None = None
        csv_path: Path | None = None

        if output_format in {"json", "both"}:
            json_path = self._base_dir / f"{sanitized_name}.json"
            rows = [record.model_dump(mode="json") for record in records]
            json_path.write_text(_dump_json_pretty(cast(JsonValue, rows)), encoding="utf-8")

        if output_format in {"csv", "both"}:
            csv_path = self._base_dir / f"{sanitized_name}.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(self._CSV_HEADERS))
                writer.writeheader()
                for record in records:
                    writer.writerow(
                        {
                            "canonical_item_id": record.canonical_item_id,
                            "weapon": record.weapon,
                            "skin_name": record.skin_name,
                            "wear": record.wear,
                            "is_stattrak": record.is_stattrak,
                            "is_souvenir": record.is_souvenir,
                            "rarity": record.rarity,
                            "collection": record.collection,
                            "source_keys": _dump_json_compact(cast(JsonValue, record.source_keys)),
                            "metadata": _dump_json_compact(cast(JsonValue, record.metadata)),
                        }
                    )

        return CatalogPersistenceResult(records=records, json_path=json_path, csv_path=csv_path)