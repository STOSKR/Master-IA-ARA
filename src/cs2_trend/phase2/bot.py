"""Multidomain scraping bot with source-constrained concurrency.

Concurrency model:
- Parallel execution across different platforms.
- Sequential execution for multiple requests within the same platform,
  with an explicit delay between consecutive requests.
"""

from __future__ import annotations

import asyncio
import csv
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from cs2_trend.core.config import AppConfig
from cs2_trend.phase1.catalog_loader import load_targets_from_catalog, resolve_catalog_path
from cs2_trend.phase1.connector_setup import (
    build_default_connectors,
    ensure_sources_are_configured,
    normalize_sources,
)
from extraction.http import HttpxAsyncClient
from extraction.models import (
    ConnectorExtraction,
    ExtractionRunResult,
    ExtractionTarget,
)
from extraction.protocols import MarketConnector


@dataclass(frozen=True, slots=True)
class MultidomainBotResult:
    """Summary output for one multidomain bot execution."""

    run_id: str
    total_jobs: int
    success_count: int
    failure_count: int
    raw_row_count: int
    raw_paths: tuple[Path, ...]
    curated_paths: tuple[Path, ...]
    raw_json_paths: tuple[Path, ...]
    curated_json_paths: tuple[Path, ...]
    metrics_path: Path


async def execute_source_constrained_extraction(
    *,
    connectors: Sequence[MarketConnector],
    targets: Sequence[ExtractionTarget],
    delay_seconds: float,
) -> tuple[ExtractionRunResult, ...]:
    """Run extraction with parallelism across sources and sequential calls per source."""

    tasks = [
        asyncio.create_task(
            _extract_source_sequentially(
                connector=connector,
                targets=targets,
                delay_seconds=delay_seconds,
            )
        )
        for connector in connectors
    ]

    if not tasks:
        return ()

    grouped_results = await asyncio.gather(*tasks)
    return tuple(result for group in grouped_results for result in group)


async def run_multidomain_scraper_bot(
    *,
    config: AppConfig,
    selected_sources: Sequence[str],
    limit_items: int,
    catalog_path: Path | None,
    delay_seconds: float,
    max_json_rows_per_file: int,
) -> MultidomainBotResult:
    """Execute full bot flow: extract, validate, and persist outputs."""

    normalized_sources = normalize_sources(selected_sources)
    ensure_sources_are_configured(config=config, selected_sources=normalized_sources)

    resolved_catalog_path = resolve_catalog_path(
        catalog_dir=config.catalog_dir,
        catalog_path=catalog_path,
    )
    targets = load_targets_from_catalog(
        catalog_path=resolved_catalog_path,
        limit_items=limit_items,
    )

    run_id = uuid4().hex
    run_started_at = datetime.now(tz=UTC)

    http_client = HttpxAsyncClient(timeout_seconds=config.http_timeout_seconds)
    try:
        connectors = tuple(
            build_default_connectors(
                config=config,
                selected_sources=normalized_sources,
                http_client=http_client,
            )
        )

        if not connectors:
            raise ValueError("No connectors could be created for selected sources")

        results = await execute_source_constrained_extraction(
            connectors=connectors,
            targets=targets,
            delay_seconds=delay_seconds,
        )
    finally:
        await http_client.aclose()

    run_finished_at = datetime.now(tz=UTC)
    success_count = sum(1 for result in results if result.success)
    failure_count = len(results) - success_count

    raw_rows = _build_raw_rows(results)
    validated_raw_rows = _validate_rows(raw_rows)
    curated_rows = _build_curated_rows(validated_raw_rows)
    validated_curated_rows = _validate_rows(curated_rows)

    timestamp = datetime.now(tz=UTC)

    raw_paths = _write_rows_by_source_csv(
        rows=validated_raw_rows,
        root_dir=config.raw_dir,
        run_id=run_id,
        timestamp=timestamp,
        curated=False,
    )
    curated_paths = _write_rows_by_source_csv(
        rows=validated_curated_rows,
        root_dir=config.curated_dir,
        run_id=run_id,
        timestamp=timestamp,
        curated=True,
    )
    raw_json_paths = _write_rows_json_shards(
        rows=validated_raw_rows,
        root_dir=config.raw_dir,
        run_id=run_id,
        timestamp=timestamp,
        curated=False,
        max_rows_per_file=max_json_rows_per_file,
    )
    curated_json_paths = _write_rows_json_shards(
        rows=validated_curated_rows,
        root_dir=config.curated_dir,
        run_id=run_id,
        timestamp=timestamp,
        curated=True,
        max_rows_per_file=max_json_rows_per_file,
    )

    metrics_path = _write_metrics(
        run_id=run_id,
        started_at=run_started_at,
        finished_at=run_finished_at,
        total_jobs=len(results),
        success_count=success_count,
        failure_count=failure_count,
        results=results,
        data_dir=config.data_dir,
    )

    return MultidomainBotResult(
        run_id=run_id,
        total_jobs=len(results),
        success_count=success_count,
        failure_count=failure_count,
        raw_row_count=len(validated_raw_rows),
        raw_paths=raw_paths,
        curated_paths=curated_paths,
        raw_json_paths=raw_json_paths,
        curated_json_paths=curated_json_paths,
        metrics_path=metrics_path,
    )


async def _extract_source_sequentially(
    *,
    connector: MarketConnector,
    targets: Sequence[ExtractionTarget],
    delay_seconds: float,
) -> tuple[ExtractionRunResult, ...]:
    source_results: list[ExtractionRunResult] = []

    for index, target in enumerate(targets):
        started_at = datetime.now(tz=UTC)
        attempts = 1
        try:
            extraction = await connector.extract(target)
            result = _success_result(
                extraction=extraction,
                attempts=attempts,
                started_at=started_at,
                finished_at=datetime.now(tz=UTC),
            )
        except Exception as exc:  # noqa: BLE001 - preserve pipeline continuity by source
            result = _failure_result(
                source_name=connector.source_name,
                target=target,
                attempts=attempts,
                started_at=started_at,
                finished_at=datetime.now(tz=UTC),
                error=exc,
            )

        source_results.append(result)

        if delay_seconds > 0 and index < len(targets) - 1:
            await asyncio.sleep(delay_seconds)

    return tuple(source_results)


def _success_result(
    *,
    extraction: ConnectorExtraction,
    attempts: int,
    started_at: datetime,
    finished_at: datetime,
) -> ExtractionRunResult:
    return ExtractionRunResult(
        source_name=extraction.source_name,
        target=extraction.target,
        success=True,
        attempts=attempts,
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=(finished_at - started_at).total_seconds(),
        extraction=extraction,
    )


def _failure_result(
    *,
    source_name: str,
    target: ExtractionTarget,
    attempts: int,
    started_at: datetime,
    finished_at: datetime,
    error: Exception,
) -> ExtractionRunResult:
    return ExtractionRunResult(
        source_name=source_name,
        target=target,
        success=False,
        attempts=attempts,
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=(finished_at - started_at).total_seconds(),
        error_type=type(error).__name__,
        error_message=str(error),
    )


def _build_raw_rows(results: Sequence[ExtractionRunResult]) -> list[dict[str, object | None]]:
    rows: list[dict[str, object | None]] = []
    for result in results:
        if not result.success or result.extraction is None:
            continue

        canonical_item_id = _resolve_canonical_item_id(result.target)
        for point in result.extraction.points:
            context = result.target.context
            rows.append(
                {
                    "timestamp_utc": point.timestamp.astimezone(UTC).isoformat(),
                    "source": result.source_name,
                    "canonical_item_id": canonical_item_id,
                    "price": float(point.price),
                    "currency": point.currency.strip().upper(),
                    "price_basis": "listing",
                    "volume": float(point.volume) if point.volume is not None else None,
                    "availability": None,
                    "object_type": _as_optional_str(context.get("object_type")),
                    "object_subtype": _as_optional_str(context.get("object_subtype")),
                    "type_name": _as_optional_str(context.get("type_name")),
                }
            )

    rows.sort(
        key=lambda row: (
            str(row.get("timestamp_utc")),
            str(row.get("source")),
            str(row.get("canonical_item_id")),
        )
    )
    return rows


def _build_curated_rows(raw_rows: Sequence[dict[str, object | None]]) -> list[dict[str, object | None]]:
    deduplicated: list[dict[str, object | None]] = []
    seen: set[tuple[str, str, str, str, str]] = set()

    for row in raw_rows:
        dedupe_key = (
            str(row.get("timestamp_utc")),
            str(row.get("source")),
            str(row.get("canonical_item_id")),
            str(row.get("currency")),
            str(row.get("price_basis")),
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        deduplicated.append(dict(row))

    grouped_indexes: dict[tuple[str, str, str, str], list[int]] = {}
    for index, row in enumerate(deduplicated):
        group_key = (
            str(row.get("source")),
            str(row.get("canonical_item_id")),
            str(row.get("currency")),
            str(row.get("price_basis")),
        )
        grouped_indexes.setdefault(group_key, []).append(index)

    for indexes in grouped_indexes.values():
        prices = [float(deduplicated[i]["price"]) for i in indexes]
        lower, upper = _iqr_bounds(prices)
        for i in indexes:
            current_price = float(deduplicated[i]["price"])
            deduplicated[i]["price"] = max(lower, min(upper, current_price))

    return deduplicated


def _validate_rows(rows: Sequence[dict[str, object | None]]) -> list[dict[str, object | None]]:
    validated: list[dict[str, object | None]] = []
    required_fields = (
        "timestamp_utc",
        "source",
        "canonical_item_id",
        "price",
        "currency",
        "price_basis",
    )

    for row in rows:
        if any(field not in row for field in required_fields):
            continue

        source = _as_optional_str(row.get("source"))
        canonical_item_id = _as_optional_str(row.get("canonical_item_id"))
        currency = _as_optional_str(row.get("currency"))
        price_basis = _as_optional_str(row.get("price_basis"))
        timestamp_utc = _as_optional_str(row.get("timestamp_utc"))
        price = row.get("price")

        if (
            source is None
            or canonical_item_id is None
            or currency is None
            or price_basis is None
            or timestamp_utc is None
        ):
            continue
        if not _is_iso_timestamp(timestamp_utc):
            continue
        if not isinstance(price, (int, float)) or not math.isfinite(float(price)):
            continue
        if float(price) <= 0:
            continue
        if len(currency) != 3:
            continue

        normalized = dict(row)
        normalized["source"] = source.lower()
        normalized["canonical_item_id"] = canonical_item_id
        normalized["currency"] = currency.upper()
        normalized["price_basis"] = price_basis
        normalized["price"] = float(price)
        validated.append(normalized)

    return validated


def _write_rows_by_source_csv(
    *,
    rows: Sequence[dict[str, object | None]],
    root_dir: Path,
    run_id: str,
    timestamp: datetime,
    curated: bool,
) -> tuple[Path, ...]:
    if not rows:
        return ()

    file_name = "historical_prices_curated.csv" if curated else "historical_prices_raw.csv"
    grouped: dict[str, list[dict[str, object | None]]] = {}
    for row in rows:
        source = str(row.get("source"))
        grouped.setdefault(source, []).append(row)

    output_paths: list[Path] = []
    for source, source_rows in sorted(grouped.items()):
        target_dir = _partition_dir(
            root_dir=root_dir,
            timestamp=timestamp,
            source=source,
            run_id=run_id,
        )
        output_path = target_dir / file_name
        fieldnames = list(source_rows[0].keys())
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(source_rows)
        output_paths.append(output_path)

    return tuple(output_paths)


def _write_rows_json_shards(
    *,
    rows: Sequence[dict[str, object | None]],
    root_dir: Path,
    run_id: str,
    timestamp: datetime,
    curated: bool,
    max_rows_per_file: int,
) -> tuple[Path, ...]:
    if not rows:
        return ()
    if max_rows_per_file < 1:
        raise ValueError("max_rows_per_file must be >= 1")

    file_prefix = "historical_prices_curated" if curated else "historical_prices_raw"
    grouped: dict[tuple[str, str], list[dict[str, object | None]]] = {}
    for row in rows:
        source = str(row.get("source"))
        object_type = str(row.get("object_type") or "unknown")
        grouped.setdefault((source, object_type), []).append(row)

    output_paths: list[Path] = []
    for (source, object_type), grouped_rows in sorted(grouped.items()):
        target_dir = _partition_dir(
            root_dir=root_dir,
            timestamp=timestamp,
            source=source,
            run_id=run_id,
        )
        shard_dir = target_dir / f"category={_sanitize_component(object_type)}"
        shard_dir.mkdir(parents=True, exist_ok=True)

        ordered = sorted(
            grouped_rows,
            key=lambda row: (
                str(row.get("timestamp_utc")),
                str(row.get("canonical_item_id")),
            ),
        )
        for shard_index, start in enumerate(range(0, len(ordered), max_rows_per_file), start=1):
            chunk = ordered[start : start + max_rows_per_file]
            output_path = shard_dir / f"{file_prefix}_part_{shard_index:04d}.json"
            output_path.write_text(json.dumps(chunk, indent=2, ensure_ascii=True), encoding="utf-8")
            output_paths.append(output_path)

    return tuple(output_paths)


def _write_metrics(
    *,
    run_id: str,
    started_at: datetime,
    finished_at: datetime,
    total_jobs: int,
    success_count: int,
    failure_count: int,
    results: Sequence[ExtractionRunResult],
    data_dir: Path,
) -> Path:
    per_source: dict[str, dict[str, int]] = {}
    for result in results:
        source = result.source_name
        bucket = per_source.setdefault(source, {"success_count": 0, "failure_count": 0})
        if result.success:
            bucket["success_count"] += 1
        else:
            bucket["failure_count"] += 1

    payload = {
        "run_id": run_id,
        "started_at_utc": started_at.isoformat(),
        "finished_at_utc": finished_at.isoformat(),
        "duration_seconds": (finished_at - started_at).total_seconds(),
        "total_jobs": total_jobs,
        "success_count": success_count,
        "failure_count": failure_count,
        "sources": per_source,
    }

    runs_dir = data_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = runs_dir / f"{run_id}_metrics.json"
    metrics_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return metrics_path


def _partition_dir(*, root_dir: Path, timestamp: datetime, source: str, run_id: str) -> Path:
    partition = timestamp.date().isoformat()
    target_dir = root_dir / f"date={partition}" / f"source={source}" / f"run={run_id}"
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


def _resolve_canonical_item_id(target: ExtractionTarget) -> str:
    context_value = target.context.get("canonical_item_id")
    if isinstance(context_value, str) and context_value.strip():
        return context_value.strip()
    return str(target.item_id)


def _as_optional_str(value: object | None) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, (int, float)):
        return str(value)
    return None


def _is_iso_timestamp(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _percentile(values: Sequence[float], quantile: float) -> float:
    if not values:
        raise ValueError("values must not be empty")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * quantile
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    if lower_index == upper_index:
        return ordered[lower_index]
    weight = position - lower_index
    return ordered[lower_index] * (1.0 - weight) + ordered[upper_index] * weight


def _iqr_bounds(values: Sequence[float], whisker_width: float = 1.5) -> tuple[float, float]:
    q1 = _percentile(values, 0.25)
    q3 = _percentile(values, 0.75)
    iqr = q3 - q1
    return q1 - whisker_width * iqr, q3 + whisker_width * iqr


def _sanitize_component(value: str) -> str:
    allowed = []
    for char in value.lower().strip():
        if char.isalnum():
            allowed.append(char)
        elif char in {"-", "_"}:
            allowed.append(char)
        else:
            allowed.append("-")

    collapsed = "".join(allowed).strip("-")
    while "--" in collapsed:
        collapsed = collapsed.replace("--", "-")
    return collapsed or "unknown"
