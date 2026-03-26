"""Command line interface for CS2 trend project phases."""

import asyncio
import os
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import typer

from cs2_trend.core.config import AppConfig, ensure_runtime_directories, load_config
from cs2_trend.core.logging import configure_logging, get_logger
from cs2_trend.core.retry import RetryPolicy, run_with_retry
from cs2_trend.core.run_context import RunContext
from cs2_trend.core.seed import set_global_seed
from cs2_trend.phase0.discovery import (
    build_discovery_summary,
    build_missing_fields_report,
    discover_catalog_records_from_external_dataset,
    discover_catalog_records_from_payload,
    find_low_volume_categories,
    has_missing_fields,
    merge_catalog_records,
    write_discovery_outputs,
)
from cs2_trend.phase0.http_clients import UrllibJsonHttpClient
from cs2_trend.phase0.models import JsonValue
from cs2_trend.phase0.repositories import FileCatalogRepository, FileProbeDumpRepository
from cs2_trend.phase0.services import (
    CatalogService,
    CsfloatCatalogParser,
    CsfloatProbeService,
)

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


_EXTERNAL_REFERENCE_ENDPOINTS: dict[str, str] = {
    "weapon": (
        "https://raw.githubusercontent.com/ByMykel/CSGO-API/main/public/api/"
        "en/skins_not_grouped.json"
    ),
    "sticker": (
        "https://raw.githubusercontent.com/ByMykel/CSGO-API/main/public/api/"
        "en/stickers.json"
    ),
    "container": (
        "https://raw.githubusercontent.com/ByMykel/CSGO-API/main/public/api/"
        "en/crates.json"
    ),
    "agent": (
        "https://raw.githubusercontent.com/ByMykel/CSGO-API/main/public/api/"
        "en/agents.json"
    ),
    "charm": (
        "https://raw.githubusercontent.com/ByMykel/CSGO-API/main/public/api/"
        "en/keychains.json"
    ),
}

_MINIMUM_DISCOVERY_COUNTS: dict[str, int] = {
    "weapon": 1000,
    "sticker": 500,
    "container": 50,
    "agent": 20,
    "charm": 30,
}


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
    source: Annotated[
        str, typer.Argument(..., help="Source to probe (example: csfloat).")
    ],
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
    probe_headers: dict[str, str] = {}
    api_key = os.getenv("CSFLOAT_API_KEY")
    cookie = os.getenv("CSFLOAT_COOKIE")
    custom_user_agent = os.getenv("CSFLOAT_USER_AGENT")
    if api_key:
        probe_headers["Authorization"] = api_key
    if cookie:
        probe_headers["Cookie"] = cookie
    if custom_user_agent:
        probe_headers["User-Agent"] = custom_user_agent

    dump_store = FileProbeDumpRepository(base_dir=config.probe_dump_dir)
    probe_service = CsfloatProbeService(
        http_client=UrllibJsonHttpClient(timeout_seconds=config.http_timeout_seconds),
        dump_store=dump_store,
        fallback_dump_dir=config.dump_dir,
        retry_policy=RetryPolicy(),
        request_headers=probe_headers,
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
        raise typer.BadParameter(
            "No probe dump found. Run `cs2trend phase0 probe csfloat` first."
        )

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


@phase0_app.command("discover")
def phase0_discover(
    ctx: typer.Context,
    endpoint: Annotated[
        str | None,
        typer.Option(
            "--endpoint",
            help="Base CSFloat endpoint for discovery (default: configured probe endpoint).",
        ),
    ] = None,
    max_pages: Annotated[
        int,
        typer.Option(
            "--max-pages",
            min=1,
            help="Maximum paginated result pages to inspect.",
        ),
    ] = 30,
    page_limit: Annotated[
        int,
        typer.Option(
            "--page-limit",
            min=1,
            max=50,
            help="Listings page size per request (CSFloat max is typically 50).",
        ),
    ] = 50,
    output_name: Annotated[
        str,
        typer.Option(
            "--output-name",
            "-o",
            help="Base output filename under data/catalog/.",
        ),
    ] = "master_catalog_possibilities",
    recursive_fallback: Annotated[
        bool,
        typer.Option(
            "--recursive-fallback/--no-recursive-fallback",
            help=(
                "Augment low-volume categories recursively using external "
                "reference datasets."
            ),
        ),
    ] = True,
) -> None:
    """Discover full catalog possibilities from paginated CSFloat listings payloads."""

    config, run_context = _get_state(ctx)
    resolved_endpoint = endpoint or config.csfloat_probe_endpoint
    if resolved_endpoint is None or not resolved_endpoint.strip():
        raise typer.BadParameter(
            "CSFloat endpoint is not configured. Set --endpoint or CS2TREND_CSFLOAT_PROBE_ENDPOINT."
        )

    headers = _build_csfloat_request_headers()
    dump_store = FileProbeDumpRepository(base_dir=config.probe_dump_dir)
    http_client = UrllibJsonHttpClient(timeout_seconds=config.http_timeout_seconds)

    payloads = asyncio.run(
        _capture_discovery_payloads(
            endpoint=resolved_endpoint,
            max_pages=max_pages,
            page_limit=page_limit,
            run_id=run_context.run_id,
            http_client=http_client,
            dump_store=dump_store,
            request_headers=headers,
        )
    )

    discovered_rows: list[dict[str, object]] = []
    for payload in payloads:
        discovered_rows.extend(discover_catalog_records_from_payload(payload))

    merged_records = merge_catalog_records(tuple(discovered_rows))
    summary = build_discovery_summary(merged_records)

    external_categories: tuple[str, ...] = ()
    if recursive_fallback:
        external_categories = find_low_volume_categories(
            summary,
            _MINIMUM_DISCOVERY_COUNTS,
        )
        if external_categories:
            external_payloads = asyncio.run(
                _capture_external_reference_payloads(
                    categories=external_categories,
                    run_id=run_context.run_id,
                    http_client=http_client,
                    dump_store=dump_store,
                )
            )
            for object_type, external_payload in external_payloads:
                discovered_rows.extend(
                    discover_catalog_records_from_external_dataset(
                        object_type=object_type,
                        payload=external_payload,
                    )
                )

            merged_records = merge_catalog_records(tuple(discovered_rows))
            summary = build_discovery_summary(merged_records)

    missing_fields = build_missing_fields_report(merged_records)
    output_paths = write_discovery_outputs(
        base_dir=config.catalog_dir,
        output_name=output_name,
        records=merged_records,
        summary=summary,
        missing_fields=missing_fields,
        include_missing_report=has_missing_fields(missing_fields),
    )

    logger = get_logger(__name__)
    logger.info(
        "phase0 discovery completed",
        extra={
            "run_id": run_context.run_id,
            "pages": len(payloads),
            "record_count": len(discovered_rows),
            "unique_record_count": len(merged_records),
            "output_name": output_name,
            "recursive_fallback": recursive_fallback,
            "external_category_count": len(external_categories),
        },
    )

    typer.echo(
        "Catalog discovery completed: "
        f"pages={len(payloads)} discovered={len(discovered_rows)} unique={len(merged_records)}"
    )
    if external_categories:
        typer.echo("- recursive_fallback categories=" + ", ".join(external_categories))
    for label, path in output_paths.items():
        typer.echo(f"- {label}: {path}")


@phase1_app.command("extract")
def phase1_extract(
    ctx: typer.Context,
    source: Annotated[
        list[str] | None,
        typer.Option("--source", "-s", help="Source filters."),
    ] = None,
    limit_items: Annotated[int, typer.Option("--limit-items", min=1)] = 50,
    catalog_file: Annotated[
        Path | None,
        typer.Option(
            "--catalog-file",
            "-c",
            help="Catalog JSON/CSV path. Defaults to latest JSON in data/catalog/.",
        ),
    ] = None,
    max_iterations: Annotated[
        int,
        typer.Option(
            "--max-iterations",
            min=1,
            help="Maximum autonomous extraction iterations with quality validation.",
        ),
    ] = 3,
    min_success_rate: Annotated[
        float,
        typer.Option(
            "--min-success-rate",
            min=0.0,
            max=1.0,
            help="Minimum success rate required to pass iterative validation.",
        ),
    ] = 0.85,
    min_raw_rows: Annotated[
        int,
        typer.Option(
            "--min-raw-rows",
            min=0,
            help="Minimum number of raw rows required to pass iterative validation.",
        ),
    ] = 100,
    max_json_rows: Annotated[
        int,
        typer.Option(
            "--max-json-rows",
            min=1,
            help="Maximum rows per persisted JSON shard file.",
        ),
    ] = 2000,
) -> None:
    """Run asynchronous historical extraction with quality gates and persisted outputs."""

    from cs2_trend.phase1.services import execute_phase1_extraction_iterative

    config, _ = _get_state(ctx)
    selected_sources = (
        source if source else ["steam", "steamdt", "buff163", "csmoney", "csfloat"]
    )

    try:
        result = asyncio.run(
            execute_phase1_extraction_iterative(
                config=config,
                selected_sources=selected_sources,
                limit_items=limit_items,
                catalog_path=catalog_file,
                max_iterations=max_iterations,
                min_success_rate=min_success_rate,
                min_raw_rows=min_raw_rows,
                max_json_rows_per_file=max_json_rows,
            )
        )
    except (ValueError, FileNotFoundError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    logger = get_logger(__name__)
    logger.info(
        "phase1 extract completed",
        extra={
            "run_id": result.run_id,
            "selected_sources": ",".join(selected_sources),
            "limit_items": limit_items,
            "total_jobs": result.total_jobs,
            "success_count": result.success_count,
            "failure_count": result.failure_count,
            "iteration": result.iteration,
            "success_rate": result.success_rate,
            "raw_row_count": result.raw_row_count,
            "quality_passed": result.quality_passed,
        },
    )

    typer.echo(
        "Phase1 extraction completed: "
        f"run_id={result.run_id} jobs={result.total_jobs} "
        f"success={result.success_count} failure={result.failure_count} "
        f"iteration={result.iteration} success_rate={result.success_rate:.3f} "
        f"raw_rows={result.raw_row_count} quality_passed={result.quality_passed}"
    )
    typer.echo(f"- metrics: {result.metrics_path}")
    if result.quality_report_path is not None:
        typer.echo(f"- quality_report: {result.quality_report_path}")
    for output in result.raw_paths:
        typer.echo(f"- raw: {output}")
    for output in result.raw_json_paths:
        typer.echo(f"- raw_json: {output}")
    for output in result.curated_paths:
        typer.echo(f"- curated: {output}")
    for output in result.curated_json_paths:
        typer.echo(f"- curated_json: {output}")


def main() -> None:
    """Execute CLI application."""

    app()


def _build_csfloat_request_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    api_key = os.getenv("CSFLOAT_API_KEY")
    cookie = os.getenv("CSFLOAT_COOKIE")
    custom_user_agent = os.getenv("CSFLOAT_USER_AGENT")
    if api_key:
        headers["Authorization"] = api_key
    if cookie:
        headers["Cookie"] = cookie
    if custom_user_agent:
        headers["User-Agent"] = custom_user_agent
    return headers


async def _capture_discovery_payloads(
    *,
    endpoint: str,
    max_pages: int,
    page_limit: int,
    run_id: str,
    http_client: UrllibJsonHttpClient,
    dump_store: FileProbeDumpRepository,
    request_headers: dict[str, str],
) -> tuple[JsonValue, ...]:
    payloads: list[JsonValue] = []
    cursor: str | None = None

    for _ in range(max_pages):
        page_endpoint = _with_query_params(
            endpoint,
            {
                "limit": str(page_limit),
                **({"cursor": cursor} if cursor else {}),
            },
        )
        response = await http_client.fetch_json(
            endpoint=page_endpoint,
            headers=request_headers,
        )

        dump_store.write_probe_dump(
            source="csfloat",
            endpoint=page_endpoint,
            run_id=run_id,
            status_code=response.status_code,
            payload=response.payload,
        )

        if response.status_code >= 400:
            raise RuntimeError(
                "CSFloat discovery request failed "
                f"status={response.status_code} endpoint={page_endpoint}"
            )

        payloads.append(response.payload)

        rows = _payload_row_count(response.payload)
        next_cursor = _payload_cursor(response.payload)
        if rows == 0 or next_cursor is None or next_cursor == cursor:
            break
        cursor = next_cursor

    return tuple(payloads)


async def _capture_external_reference_payloads(
    *,
    categories: tuple[str, ...],
    run_id: str,
    http_client: UrllibJsonHttpClient,
    dump_store: FileProbeDumpRepository,
) -> tuple[tuple[str, JsonValue], ...]:
    tasks = [
        _fetch_external_reference_category(
            category=category,
            run_id=run_id,
            http_client=http_client,
            dump_store=dump_store,
        )
        for category in categories
        if category in _EXTERNAL_REFERENCE_ENDPOINTS
    ]
    if not tasks:
        return ()
    results = await asyncio.gather(*tasks)
    return tuple(results)


async def _fetch_external_reference_category(
    *,
    category: str,
    run_id: str,
    http_client: UrllibJsonHttpClient,
    dump_store: FileProbeDumpRepository,
) -> tuple[str, JsonValue]:
    endpoint = _EXTERNAL_REFERENCE_ENDPOINTS[category]
    logger = get_logger(__name__)

    async def _operation() -> Any:
        return await http_client.fetch_json(endpoint=endpoint)

    response = await run_with_retry(
        _operation,
        RetryPolicy(max_attempts=3, base_delay_seconds=0.8, exponential_factor=2.0),
        on_retry=(
            lambda attempt, exc, delay: logger.warning(
                "external category fetch retry",
                extra={
                    "category": category,
                    "attempt": attempt,
                    "delay_seconds": round(delay, 3),
                    "error": str(exc),
                },
            )
        ),
    )

    if response.status_code >= 400:
        raise RuntimeError(
            "External category fetch failed "
            f"category={category} status={response.status_code} endpoint={endpoint}"
        )

    dump_store.write_probe_dump(
        source=f"external_{category}",
        endpoint=endpoint,
        run_id=run_id,
        status_code=response.status_code,
        payload=response.payload,
    )
    return category, response.payload


def _with_query_params(endpoint: str, params: dict[str, str]) -> str:
    parsed = urlsplit(endpoint)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update(params)
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(query),
            parsed.fragment,
        )
    )


def _payload_row_count(payload: JsonValue) -> int:
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return len(data)
    return 0


def _payload_cursor(payload: JsonValue) -> str | None:
    if isinstance(payload, dict):
        cursor = payload.get("cursor")
        if isinstance(cursor, str) and cursor.strip():
            return cursor.strip()
    return None
