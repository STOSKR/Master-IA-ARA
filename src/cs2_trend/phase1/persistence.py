from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from cs2_price_trend.quality import (
    drop_duplicate_rows,
    normalize_source,
    sanitize_price_outliers_iqr,
)
from cs2_price_trend.reliability.run_metrics import build_run_metrics
from cs2_price_trend.storage.paths import (
    StorageRoots,
    curated_run_partition_dir,
    raw_run_partition_dir,
)
from cs2_trend.core.pathing import sanitize_component
from extraction.models import ExtractionRun


def build_curated_frame(raw_frame: pd.DataFrame) -> pd.DataFrame:
    """Generate curated frame by dropping duplicates and sanitizing outliers."""

    if raw_frame.empty:
        return raw_frame

    deduplicated = drop_duplicate_rows(raw_frame)
    return sanitize_price_outliers_iqr(deduplicated)


def write_frame_by_source_csv(
    *,
    frame: pd.DataFrame,
    roots: StorageRoots,
    run_id: str,
    timestamp: datetime,
    curated: bool,
) -> tuple[Path, ...]:
    """Write one CSV file per source and return output paths."""

    if frame.empty:
        return tuple()

    file_name = "historical_prices_curated.csv" if curated else "historical_prices_raw.csv"
    date_partition = timestamp.date()
    partition_resolver = curated_run_partition_dir if curated else raw_run_partition_dir

    written_paths: list[Path] = []
    for source, source_frame in frame.groupby("source", sort=True):
        normalized_source = normalize_source(str(source))
        directory = partition_resolver(
            roots,
            date_partition,
            normalized_source,
            run_id,
            create=True,
        )

        output_path = directory / file_name
        source_frame.to_csv(output_path, index=False)
        written_paths.append(output_path)

    return tuple(written_paths)


def write_frame_json_shards(
    *,
    frame: pd.DataFrame,
    roots: StorageRoots,
    run_id: str,
    timestamp: datetime,
    curated: bool,
    max_rows_per_file: int,
) -> tuple[Path, ...]:
    """Write shard JSON files partitioned by source/category for manageable size."""

    if frame.empty:
        return tuple()
    if max_rows_per_file < 1:
        raise ValueError("max_rows_per_file must be >= 1")

    file_prefix = "historical_prices_curated" if curated else "historical_prices_raw"
    date_partition = timestamp.date()
    partition_resolver = curated_run_partition_dir if curated else raw_run_partition_dir

    working = frame.copy()
    if "object_type" not in working.columns:
        working["object_type"] = "unknown"

    written_paths: list[Path] = []
    for (source, object_type), group in working.groupby(["source", "object_type"], sort=True):
        normalized_source = normalize_source(str(source))
        category_slug = sanitize_component(str(object_type))
        root_dir = partition_resolver(
            roots,
            date_partition,
            normalized_source,
            run_id,
            create=True,
        )
        shard_dir = root_dir / f"category={category_slug}"
        shard_dir.mkdir(parents=True, exist_ok=True)

        ordered = group.sort_values(
            by=["timestamp_utc", "canonical_item_id"],
            kind="stable",
        ).reset_index(drop=True)

        for part_index, start in enumerate(range(0, len(ordered), max_rows_per_file), start=1):
            chunk = ordered.iloc[start : start + max_rows_per_file]
            payload = _to_json_records(chunk)
            output_path = shard_dir / f"{file_prefix}_part_{part_index:04d}.json"
            output_path.write_text(
                json.dumps(payload, ensure_ascii=True, indent=2),
                encoding="utf-8",
            )
            written_paths.append(output_path)

    return tuple(written_paths)


def write_metrics(
    *,
    run_output: ExtractionRun,
    data_dir: Path,
    selected_sources: Sequence[str],
) -> Path:
    """Write run metrics in JSON format and return output path."""

    metrics = build_run_metrics(run_output.metrics.run_id)
    source_set = {normalize_source(source) for source in selected_sources}

    for result in run_output.results:
        if result.source_name not in source_set:
            continue
        if result.success:
            metrics.record_success(result.source_name)
        else:
            metrics.record_failure(result.source_name)

    payload: dict[str, Any] = dict(metrics.as_observability_payload())
    payload["total_jobs"] = run_output.metrics.total_jobs

    runs_dir = data_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = runs_dir / f"{run_output.metrics.run_id}_metrics.json"
    metrics_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return metrics_path


def write_quality_report(
    *,
    data_dir: Path,
    run_id: str,
    min_success_rate: float,
    min_raw_rows: int,
    iterations: Sequence[dict[str, Any]],
) -> Path:
    """Persist iterative quality evaluation report for traceability."""

    runs_dir = data_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    report_path = runs_dir / f"{run_id}_quality_report.json"

    payload: dict[str, Any] = {
        "generated_at_utc": datetime.now(tz=UTC).isoformat(),
        "criteria": {
            "min_success_rate": min_success_rate,
            "min_raw_rows": min_raw_rows,
            "require_zero_failures": True,
        },
        "iterations": list(iterations),
        "final_passed": bool(iterations and iterations[-1].get("passed", False)),
    }
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return report_path


def _to_json_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    for row in frame.to_dict(orient="records"):
        normalized: dict[str, Any] = {}
        for key, value in row.items():
            normalized[key] = _normalize_json_value(value)
        records.append(normalized)

    return records


def _normalize_json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, pd.Timestamp):
        return value.tz_convert("UTC").isoformat() if value.tzinfo else value.isoformat()
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except (TypeError, ValueError):
            return value
    return value
