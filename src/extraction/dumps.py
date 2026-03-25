from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(slots=True, frozen=True)
class AnomalyDumpContext:
    """Context metadata attached to every anomaly dump."""

    source_name: str
    item_id: str
    reason: str
    attempt: int
    response_status: int | None = None
    response_url: str | None = None


class AnomalyDumper:
    """Persist raw failure payloads for later inspection."""

    def __init__(self, base_dir: Path | str = Path(".dumps")) -> None:
        self._base_dir = Path(base_dir)

    def dump_raw_failure(self, raw_body: bytes | None, context: AnomalyDumpContext) -> Path:
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S%fZ")
        source_dir = self._base_dir / context.source_name
        source_dir.mkdir(parents=True, exist_ok=True)

        file_path = source_dir / f"{timestamp}_{context.item_id}_attempt{context.attempt}.dump"
        payload = self._format_dump(raw_body=raw_body, context=context)
        file_path.write_bytes(payload)
        return file_path

    def _format_dump(self, raw_body: bytes | None, context: AnomalyDumpContext) -> bytes:
        header_lines = [
            f"source={context.source_name}",
            f"item_id={context.item_id}",
            f"attempt={context.attempt}",
            f"reason={context.reason}",
            f"response_status={context.response_status}",
            f"response_url={context.response_url}",
            "---",
            "",
        ]
        header = "\n".join(header_lines).encode("utf-8", errors="replace")
        return header + (raw_body or b"")
