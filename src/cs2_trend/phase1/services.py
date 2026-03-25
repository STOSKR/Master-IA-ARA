"""Phase 1 orchestration: catalog-driven extraction, quality gates, and persistence."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

from cs2_price_trend.quality import (
    drop_duplicate_rows,
    normalize_source,
    sanitize_price_outliers_iqr,
    validate_history_dataframe,
)
from cs2_price_trend.quality.transforms import extraction_results_to_history_frame
from cs2_price_trend.reliability.run_metrics import build_run_metrics
from cs2_price_trend.storage.paths import (
    StorageRoots,
    curated_run_partition_dir,
    raw_run_partition_dir,
)
from cs2_trend.core.config import AppConfig
from extraction.connectors import (
    Buff163Connector,
    CSFloatConnector,
    CSMoneyConnector,
    SteamConnector,
    SteamdtConnector,
)
from extraction.http import HttpxAsyncClient
from extraction.kernel import AsyncExtractionKernel, KernelConfig
from extraction.models import ExtractionRun, ExtractionTarget
from extraction.protocols import AsyncHttpClient, MarketConnector

_SOURCE_TO_ENV: dict[str, str] = {
    "steam": "STEAM_PROBE_ENDPOINT",
    "steamdt": "STEAMDT_PROBE_ENDPOINT",
    "buff163": "BUFF163_PROBE_ENDPOINT",
    "csmoney": "CSMONEY_PROBE_ENDPOINT",
    "csfloat": "CSFLOAT_PROBE_ENDPOINT",
}

_CSFLOAT_AUTH_ENV_NAMES: tuple[str, ...] = ("CSFLOAT_API_KEY", "CSFLOAT_COOKIE")


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


async def execute_phase1_extraction(
    *,
    config: AppConfig,
    selected_sources: Sequence[str],
    limit_items: int,
    catalog_path: Path | None,
    connector_factory: ConnectorFactory | None = None,
) -> Phase1ExecutionResult:
    """Run phase 1 extraction using selected sources and a canonical catalog."""

    normalized_sources = _normalize_sources(selected_sources)
    _ensure_sources_are_configured(config=config, selected_sources=normalized_sources)

    resolved_catalog_path = _resolve_catalog_path(
        catalog_dir=config.catalog_dir,
        catalog_path=catalog_path,
    )
    targets = _load_targets_from_catalog(
        catalog_path=resolved_catalog_path, limit_items=limit_items
    )

    http_client = HttpxAsyncClient(timeout_seconds=config.http_timeout_seconds)
    try:
        factory = connector_factory or _build_default_connectors
        connectors = tuple(
            factory(
                config=config,
                selected_sources=normalized_sources,
                http_client=http_client,
            )
        )
        if not connectors:
            raise ValueError("No connectors could be created for the selected sources")

        run_output = await _run_kernel(
            connectors=connectors,
            targets=targets,
            config=config,
        )
    finally:
        await http_client.aclose()

    raw_frame = extraction_results_to_history_frame(run_output.results)
    validated_raw = validate_history_dataframe(raw_frame)
    curated_frame = _build_curated_frame(raw_frame)
    validated_curated = validate_history_dataframe(curated_frame)

    timestamp = datetime.now(tz=UTC)
    roots = StorageRoots(
        raw_root=config.raw_dir,
        curated_root=config.curated_dir,
        dumps_root=config.dump_dir,
    ).expanded()

    raw_paths = _write_frame_by_source(
        frame=validated_raw,
        roots=roots,
        run_id=run_output.metrics.run_id,
        timestamp=timestamp,
        curated=False,
    )
    curated_paths = _write_frame_by_source(
        frame=validated_curated,
        roots=roots,
        run_id=run_output.metrics.run_id,
        timestamp=timestamp,
        curated=True,
    )

    metrics_path = _write_metrics(
        run_output=run_output,
        data_dir=config.data_dir,
        selected_sources=normalized_sources,
    )

    return Phase1ExecutionResult(
        run_id=run_output.metrics.run_id,
        total_jobs=run_output.metrics.total_jobs,
        success_count=run_output.metrics.success_count,
        failure_count=run_output.metrics.failure_count,
        raw_paths=raw_paths,
        curated_paths=curated_paths,
        metrics_path=metrics_path,
    )


async def _run_kernel(
    *,
    connectors: Sequence[MarketConnector],
    targets: Sequence[ExtractionTarget],
    config: AppConfig,
) -> ExtractionRun:
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


def _normalize_sources(selected_sources: Sequence[str]) -> tuple[str, ...]:
    if not selected_sources:
        selected_sources = ("steam", "steamdt", "buff163", "csmoney", "csfloat")

    normalized = tuple(normalize_source(source) for source in selected_sources)
    return tuple(dict.fromkeys(normalized))


def _resolve_catalog_path(*, catalog_dir: Path, catalog_path: Path | None) -> Path:
    if catalog_path is not None:
        if not catalog_path.exists():
            raise FileNotFoundError(f"Catalog file does not exist: {catalog_path}")
        return catalog_path

    json_candidates = sorted(catalog_dir.glob("*.json"), reverse=True)
    if not json_candidates:
        raise FileNotFoundError(
            "No catalog JSON files found. Run `cs2trend phase0 catalog` before phase1 extraction."
        )
    return json_candidates[0]


def _load_targets_from_catalog(
    *,
    catalog_path: Path,
    limit_items: int,
) -> tuple[ExtractionTarget, ...]:
    if limit_items < 1:
        raise ValueError("limit_items must be >= 1")

    rows = _read_catalog_rows(catalog_path)
    targets: list[ExtractionTarget] = []

    for row in rows:
        canonical_item_id = _as_str(row.get("canonical_item_id"))
        if canonical_item_id is None:
            continue

        source_keys = _coerce_json_object(row.get("source_keys"))
        metadata = _coerce_json_object(row.get("metadata"))

        market_hash_name = _resolve_market_hash_name(
            row=row,
            metadata=metadata,
            canonical_item_id=canonical_item_id,
        )
        item_id = _as_str(source_keys.get("csfloat")) or canonical_item_id

        targets.append(
            ExtractionTarget(
                item_id=item_id,
                market_hash_name=market_hash_name,
                context={
                    "canonical_item_id": canonical_item_id,
                    "currency": "USD",
                },
            )
        )

        if len(targets) >= limit_items:
            break

    if not targets:
        raise ValueError(
            f"No valid extraction targets found in catalog: {catalog_path}"
        )

    return tuple(targets)


def _read_catalog_rows(catalog_path: Path) -> tuple[dict[str, Any], ...]:
    if catalog_path.suffix.lower() == ".json":
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("Catalog JSON must contain a list of rows")
        return tuple(row for row in payload if isinstance(row, dict))

    if catalog_path.suffix.lower() == ".csv":
        frame = pd.read_csv(catalog_path)
        return tuple(dict(row) for _, row in frame.iterrows())

    raise ValueError(f"Unsupported catalog format: {catalog_path.suffix}")


def _resolve_market_hash_name(
    *,
    row: dict[str, Any],
    metadata: dict[str, Any],
    canonical_item_id: str,
) -> str:
    raw_market_name = _as_str(metadata.get("raw_market_name"))
    if raw_market_name is not None:
        return raw_market_name

    weapon = _as_str(row.get("weapon"))
    skin_name = _as_str(row.get("skin_name"))
    if weapon is not None and skin_name is not None:
        return f"{weapon} | {skin_name}"

    return canonical_item_id


def _coerce_json_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw

    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed

    return {}


def _as_str(raw: Any) -> str | None:
    if isinstance(raw, str):
        value = raw.strip()
        return value or None
    if isinstance(raw, int):
        return str(raw)
    return None


def _build_default_connectors(
    *,
    config: AppConfig,
    selected_sources: Sequence[str],
    http_client: AsyncHttpClient,
) -> Sequence[MarketConnector]:
    connector_builders: dict[str, MarketConnector] = {
        "steam": SteamConnector(
            http_client=http_client,
            endpoint=config.steam_probe_endpoint,
        ),
        "steamdt": SteamdtConnector(
            http_client=http_client,
            endpoint=config.steamdt_probe_endpoint,
        ),
        "buff163": Buff163Connector(
            http_client=http_client,
            endpoint=config.buff163_probe_endpoint,
        ),
        "csmoney": CSMoneyConnector(
            http_client=http_client,
            endpoint=config.csmoney_probe_endpoint,
        ),
        "csfloat": CSFloatConnector(
            http_client=http_client,
            endpoint=config.csfloat_history_endpoint or config.csfloat_probe_endpoint,
        ),
    }

    connectors = [
        connector_builders[source]
        for source in selected_sources
        if source in connector_builders
    ]

    return tuple(connectors)


def _ensure_sources_are_configured(
    *, config: AppConfig, selected_sources: Sequence[str]
) -> None:
    missing: list[str] = []

    for source in selected_sources:
        endpoint = _endpoint_for_source(config=config, source=source)
        env_name = _SOURCE_TO_ENV[source]
        env_value = os.getenv(env_name)

        if endpoint is None and (env_value is None or not env_value.strip()):
            missing.append(f"{source} ({env_name})")

        if source == "csfloat" and not _has_csfloat_auth():
            missing.append("csfloat authentication (CSFLOAT_API_KEY or CSFLOAT_COOKIE)")

    if missing:
        joined = ", ".join(sorted(missing))
        raise ValueError(
            "Missing endpoint configuration for selected sources: "
            f"{joined}. Set environment variables or AppConfig endpoint fields."
        )


def _has_csfloat_auth() -> bool:
    for env_name in _CSFLOAT_AUTH_ENV_NAMES:
        value = os.getenv(env_name)
        if value and value.strip():
            return True
    return False


def _endpoint_for_source(*, config: AppConfig, source: str) -> str | None:
    if source == "steam":
        return _normalized_optional(config.steam_probe_endpoint)
    if source == "steamdt":
        return _normalized_optional(config.steamdt_probe_endpoint)
    if source == "buff163":
        return _normalized_optional(config.buff163_probe_endpoint)
    if source == "csmoney":
        return _normalized_optional(config.csmoney_probe_endpoint)
    if source == "csfloat":
        return _normalized_optional(
            config.csfloat_history_endpoint or config.csfloat_probe_endpoint
        )
    raise ValueError(f"Unsupported source: {source}")


def _normalized_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _build_curated_frame(raw_frame: pd.DataFrame) -> pd.DataFrame:
    if raw_frame.empty:
        return raw_frame

    deduplicated = drop_duplicate_rows(raw_frame)
    return sanitize_price_outliers_iqr(deduplicated)


def _write_frame_by_source(
    *,
    frame: pd.DataFrame,
    roots: StorageRoots,
    run_id: str,
    timestamp: datetime,
    curated: bool,
) -> tuple[Path, ...]:
    if frame.empty:
        return tuple()

    file_name = (
        "historical_prices_curated.csv" if curated else "historical_prices_raw.csv"
    )
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


def _write_metrics(
    *,
    run_output: ExtractionRun,
    data_dir: Path,
    selected_sources: Sequence[str],
) -> Path:
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
