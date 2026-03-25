"""Command line interface for CS2 trend project phases."""

import asyncio
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from cs2_trend.core.config import AppConfig, ensure_runtime_directories, load_config
from cs2_trend.core.logging import configure_logging, get_logger
from cs2_trend.core.retry import RetryPolicy
from cs2_trend.core.run_context import RunContext
from cs2_trend.core.seed import set_global_seed
from cs2_trend.phase0.http_clients import UrllibJsonHttpClient
from cs2_trend.phase0.repositories import FileCatalogRepository, FileProbeDumpRepository
from cs2_trend.phase0.services import CatalogService, CsfloatCatalogParser, CsfloatProbeService

app = typer.Typer(help="CS2 Trend CLI", no_args_is_help=True, add_completion=False)
phase0_app = typer.Typer(help="Phase 0 foundation and catalog discovery commands")
phase1_app = typer.Typer(help="Phase 1 extraction commands")

app.add_typer(phase0_app, name="phase0")
app.add_typer(phase1_app, name="phase1")


class CatalogOutputMode(StrEnum):
    """Allowed output modes for phase0 catalog command."""

    JSON = "json"
    CSV = "csv"
    BOTH = "both"


@app.callback()
def bootstrap(ctx: typer.Context) -> None:
    """Initialize typed runtime context used by all CLI commands."""

    config = load_config()
    ensure_runtime_directories(config)
    configure_logging(config.log_level)
    set_global_seed(config.random_seed)

    ctx.obj = {
        "config": config,
        "run_context": RunContext.create(),
    }


def _get_state(ctx: typer.Context) -> tuple[AppConfig, RunContext]:
    """Return validated state values from Typer context."""

    state = ctx.obj
    if not isinstance(state, dict):
        raise typer.BadParameter("Application state is not initialized.")

    config = state.get("config")
    run_context = state.get("run_context")

    if not isinstance(config, AppConfig) or not isinstance(run_context, RunContext):
        raise typer.BadParameter("Invalid application state payload.")

    return config, run_context


@phase0_app.command("probe")
def phase0_probe(
    ctx: typer.Context,
    source: Annotated[str, typer.Argument(..., help="Source to probe (example: csfloat).")],
    sample_size: Annotated[int, typer.Option("--sample-size", "-n", min=1)] = 1,
    endpoint: Annotated[
        str | None,
        typer.Option("--endpoint", help="Override source probe endpoint."),
    ] = None,
) -> None:
    """Probe configured source endpoint and persist timestamped dump samples."""

    config, run_context = _get_state(ctx)
    normalized_source = source.strip().lower()
    if normalized_source != "csfloat":
        raise typer.BadParameter("Only csfloat source is implemented in phase0.")

    resolved_endpoint = endpoint or config.csfloat_probe_endpoint
    dump_store = FileProbeDumpRepository(base_dir=config.probe_dump_dir)
    probe_service = CsfloatProbeService(
        http_client=UrllibJsonHttpClient(timeout_seconds=config.http_timeout_seconds),
        dump_store=dump_store,
        fallback_dump_dir=config.dump_dir,
        retry_policy=RetryPolicy(),
    )

    records = asyncio.run(
        probe_service.capture_samples(
            endpoint=resolved_endpoint,
            run_id=run_context.run_id,
            sample_size=sample_size,
        )
    )

    logger = get_logger(__name__)
    logger.info(
        "phase0 probe completed",
        extra={
            "run_id": run_context.run_id,
            "source": normalized_source,
            "sample_size": sample_size,
            "endpoint": resolved_endpoint,
            "dump_count": len(records),
        },
    )
    typer.echo(f"Probe completed: source={normalized_source} samples={len(records)}")
    for record in records:
        typer.echo(f"- {record.dump_path}")


@phase0_app.command("catalog")
def phase0_catalog(
    ctx: typer.Context,
    dump_file: Annotated[
        Path | None,
        typer.Option(
            "--dump-file",
            "-d",
            help="Probe dump file to parse. Defaults to latest CSFloat probe dump.",
        ),
    ] = None,
    output_mode: Annotated[
        CatalogOutputMode,
        typer.Option(
            "--output-mode",
            "-m",
            help="Catalog output format: json, csv, or both.",
        ),
    ] = CatalogOutputMode.BOTH,
    output_name: Annotated[
        str,
        typer.Option(
            "--output-name",
            "-o",
            help="Base output filename stored under data/catalog/.",
        ),
    ] = "master_catalog",
) -> None:
    """Build canonical catalog records from probe dumps and persist tabular outputs."""

    config, run_context = _get_state(ctx)
    dump_store = FileProbeDumpRepository(base_dir=config.probe_dump_dir)
    catalog_service = CatalogService(
        parser=CsfloatCatalogParser(),
        catalog_store=FileCatalogRepository(base_dir=config.catalog_dir),
        dump_store=dump_store,
    )

    selected_dump_file = dump_file
    if selected_dump_file is None:
        selected_dump_file = catalog_service.latest_probe_path(source="csfloat")
    if selected_dump_file is None:
        raise typer.BadParameter("No probe dump found. Run `cs2trend phase0 probe csfloat` first.")

    records = catalog_service.build_catalog_from_dump(dump_path=selected_dump_file)
    result = catalog_service.persist_catalog(
        records=records,
        output_format=output_mode.value,
        base_name=output_name,
    )

    logger = get_logger(__name__)
    logger.info(
        "phase0 catalog completed",
        extra={
            "run_id": run_context.run_id,
            "dump_file": str(selected_dump_file),
            "record_count": len(records),
            "output_mode": output_mode.value,
        },
    )
    typer.echo(
        "Catalog built: "
        f"records={len(records)} source_dump={selected_dump_file} mode={output_mode.value}"
    )
    if result.json_path is not None:
        typer.echo(f"- json: {result.json_path}")
    if result.csv_path is not None:
        typer.echo(f"- csv: {result.csv_path}")


@phase1_app.command("extract")
def phase1_extract(
    ctx: typer.Context,
    source: Annotated[
        list[str] | None,
        typer.Option("--source", "-s", help="Source filters."),
    ] = None,
    limit_items: Annotated[int, typer.Option("--limit-items", min=1)] = 50,
) -> None:
    """Placeholder command for asynchronous historical extraction."""

    config, run_context = _get_state(ctx)
    selected_sources = source if source else ["steam", "steamdt", "buff163", "csmoney", "csfloat"]
    logger = get_logger(__name__)
    logger.info(
        "phase1 extract placeholder invoked",
        extra={
            "run_id": run_context.run_id,
            "selected_sources": ",".join(selected_sources),
            "limit_items": limit_items,
        },
    )
    typer.echo(
        f"[placeholder] phase1 extract sources={selected_sources} limit_items={limit_items} "
        f"dump_dir={config.dump_dir}"
    )


def main() -> None:
    """Execute CLI application."""

    app()
