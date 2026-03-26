"""Phase 1 orchestration: catalog-driven extraction, quality gates, and persistence."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from cs2_price_trend.quality import validate_history_dataframe
from cs2_price_trend.quality.transforms import extraction_results_to_history_frame
from cs2_price_trend.storage.paths import StorageRoots
from cs2_trend.core.config import AppConfig
from cs2_trend.phase1.catalog_loader import (
    load_targets_from_catalog,
    resolve_catalog_path,
)
from cs2_trend.phase1.connector_setup import (
    build_default_connectors,
    ensure_sources_are_configured,
    normalize_sources,
)
from cs2_trend.phase1.persistence import (
    build_curated_frame,
    write_frame_by_source_csv,
    write_frame_json_shards,
    write_metrics,
    write_quality_report,
)
from extraction.http import HttpxAsyncClient
from extraction.kernel import AsyncExtractionKernel, KernelConfig
from extraction.models import ExtractionRun, ExtractionTarget
from extraction.protocols import AsyncHttpClient, MarketConnector


class ConnectorFactory(Protocol):
    """Build connector instances for selected sources."""

    def __call__(
        self,
        *,
        config: AppConfig,
        selected_sources: Sequence[str],
        http_client: AsyncHttpClient,
    ) -> Sequence[MarketConnector]: ...


@dataclass(frozen=True, slots=True)
class Phase1ExecutionResult:
    """Serializable summary for one phase 1 extraction execution."""

    run_id: str
    total_jobs: int
    success_count: int
    failure_count: int
    raw_paths: tuple[Path, ...]
    curated_paths: tuple[Path, ...]
    metrics_path: Path
    raw_json_paths: tuple[Path, ...] = ()
    curated_json_paths: tuple[Path, ...] = ()
    raw_row_count: int = 0
    success_rate: float = 0.0
    iteration: int = 1
    quality_passed: bool | None = None
    quality_report_path: Path | None = None


async def execute_phase1_extraction(
    *,
    config: AppConfig,
    selected_sources: Sequence[str],
    limit_items: int,
    catalog_path: Path | None,
    connector_factory: ConnectorFactory | None = None,
    max_json_rows_per_file: int = 2000,
) -> Phase1ExecutionResult:
    """Run phase 1 extraction using selected sources and a canonical catalog."""

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

    run_output = await _run_extraction_kernel(
        config=config,
        selected_sources=normalized_sources,
        targets=targets,
        connector_factory=connector_factory,
    )

    raw_frame = extraction_results_to_history_frame(
        run_output.results,
        include_context_columns=True,
    )
    validated_raw = validate_history_dataframe(raw_frame)

    curated_frame = build_curated_frame(raw_frame)
    validated_curated = validate_history_dataframe(curated_frame)

    timestamp = datetime.now(tz=UTC)
    roots = StorageRoots(
        raw_root=config.raw_dir,
        curated_root=config.curated_dir,
        dumps_root=config.dump_dir,
    ).expanded()

    raw_paths = write_frame_by_source_csv(
        frame=validated_raw,
        roots=roots,
        run_id=run_output.metrics.run_id,
        timestamp=timestamp,
        curated=False,
    )
    curated_paths = write_frame_by_source_csv(
        frame=validated_curated,
        roots=roots,
        run_id=run_output.metrics.run_id,
        timestamp=timestamp,
        curated=True,
    )
    raw_json_paths = write_frame_json_shards(
        frame=validated_raw,
        roots=roots,
        run_id=run_output.metrics.run_id,
        timestamp=timestamp,
        curated=False,
        max_rows_per_file=max_json_rows_per_file,
    )
    curated_json_paths = write_frame_json_shards(
        frame=validated_curated,
        roots=roots,
        run_id=run_output.metrics.run_id,
        timestamp=timestamp,
        curated=True,
        max_rows_per_file=max_json_rows_per_file,
    )

    metrics_path = write_metrics(
        run_output=run_output,
        data_dir=config.data_dir,
        selected_sources=normalized_sources,
    )
    success_rate = (
        run_output.metrics.success_count / run_output.metrics.total_jobs
        if run_output.metrics.total_jobs > 0
        else 0.0
    )

    return Phase1ExecutionResult(
        run_id=run_output.metrics.run_id,
        total_jobs=run_output.metrics.total_jobs,
        success_count=run_output.metrics.success_count,
        failure_count=run_output.metrics.failure_count,
        raw_paths=raw_paths,
        curated_paths=curated_paths,
        metrics_path=metrics_path,
        raw_json_paths=raw_json_paths,
        curated_json_paths=curated_json_paths,
        raw_row_count=len(validated_raw.index),
        success_rate=success_rate,
    )


async def execute_phase1_extraction_iterative(
    *,
    config: AppConfig,
    selected_sources: Sequence[str],
    limit_items: int,
    catalog_path: Path | None,
    connector_factory: ConnectorFactory | None = None,
    max_iterations: int = 3,
    min_success_rate: float = 0.85,
    min_raw_rows: int = 100,
    max_json_rows_per_file: int = 2000,
) -> Phase1ExecutionResult:
    """Repeat extraction until quality gates pass or iteration cap is reached."""

    if max_iterations < 1:
        raise ValueError("max_iterations must be >= 1")
    if not 0.0 <= min_success_rate <= 1.0:
        raise ValueError("min_success_rate must be within [0, 1]")
    if min_raw_rows < 0:
        raise ValueError("min_raw_rows must be >= 0")

    assessments: list[dict[str, Any]] = []
    latest_result: Phase1ExecutionResult | None = None

    for iteration in range(1, max_iterations + 1):
        current_result = await execute_phase1_extraction(
            config=config,
            selected_sources=selected_sources,
            limit_items=limit_items,
            catalog_path=catalog_path,
            connector_factory=connector_factory,
            max_json_rows_per_file=max_json_rows_per_file,
        )
        current_result = replace(current_result, iteration=iteration)
        latest_result = current_result

        assessment = _evaluate_iteration(
            result=current_result,
            min_success_rate=min_success_rate,
            min_raw_rows=min_raw_rows,
        )
        assessments.append(assessment)
        if assessment["passed"]:
            break

    if latest_result is None:
        raise RuntimeError("Phase1 iterative execution produced no runs")

    quality_report_path = write_quality_report(
        data_dir=config.data_dir,
        run_id=latest_result.run_id,
        min_success_rate=min_success_rate,
        min_raw_rows=min_raw_rows,
        iterations=assessments,
    )

    final_passed = bool(assessments and assessments[-1]["passed"])
    return replace(
        latest_result,
        quality_passed=final_passed,
        quality_report_path=quality_report_path,
    )


async def _run_extraction_kernel(
    *,
    config: AppConfig,
    selected_sources: Sequence[str],
    targets: Sequence[ExtractionTarget],
    connector_factory: ConnectorFactory | None,
) -> ExtractionRun:
    http_client = HttpxAsyncClient(timeout_seconds=config.http_timeout_seconds)
    try:
        factory = connector_factory or build_default_connectors
        connectors = tuple(
            factory(
                config=config,
                selected_sources=selected_sources,
                http_client=http_client,
            )
        )
        if not connectors:
            raise ValueError("No connectors could be created for the selected sources")

        concurrency = min(
            config.phase1_max_concurrency,
            max(1, len(connectors) * max(1, len(targets))),
        )
        kernel = AsyncExtractionKernel(
            connectors=connectors,
            config=KernelConfig(
                max_concurrency=concurrency,
                dump_dir=config.dump_dir,
            ),
        )
        return await kernel.run(targets)
    finally:
        await http_client.aclose()


def _evaluate_iteration(
    *,
    result: Phase1ExecutionResult,
    min_success_rate: float,
    min_raw_rows: int,
) -> dict[str, Any]:
    reasons: list[str] = []

    if result.success_rate < min_success_rate:
        reasons.append(
            "success_rate_below_threshold "
            f"({result.success_rate:.4f} < {min_success_rate:.4f})"
        )
    if result.raw_row_count < min_raw_rows:
        reasons.append(
            f"raw_rows_below_threshold ({result.raw_row_count} < {min_raw_rows})"
        )
    if result.failure_count > 0:
        reasons.append(f"failures_present ({result.failure_count})")

    return {
        "iteration": result.iteration,
        "run_id": result.run_id,
        "timestamp_utc": datetime.now(tz=UTC).isoformat(),
        "success_rate": result.success_rate,
        "raw_row_count": result.raw_row_count,
        "total_jobs": result.total_jobs,
        "success_count": result.success_count,
        "failure_count": result.failure_count,
        "passed": not reasons,
        "reasons": reasons,
    }
