"""Utilities to persist anomalous responses for debugging."""

from datetime import UTC, datetime
from pathlib import Path

from cs2_trend.core.pathing import sanitize_component


def dump_anomalous_response(
    *,
    base_dir: Path,
    source: str,
    endpoint: str,
    run_id: str,
    body: str | bytes,
    status_code: int | None = None,
) -> Path:
    """Persist a raw anomalous response payload with timestamped metadata.

    This function is designed for extractor fallback paths where repeated retries
    still fail and the original response body must be kept for diagnostics.
    """

    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    source_part = sanitize_component(source)
    endpoint_part = sanitize_component(endpoint)
    status_part = str(status_code) if status_code is not None else "na"

    base_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"{timestamp}_{run_id}_{source_part}_{endpoint_part}_{status_part}.dump"
    dump_path = base_dir / file_name

    if isinstance(body, bytes):
        dump_path.write_bytes(body)
    else:
        dump_path.write_text(body, encoding="utf-8")

    return dump_path
