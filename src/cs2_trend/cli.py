"""Command line interface for CS2 trend project phases."""

from pathlib import Path

import typer

from cs2_trend.core.config import AppConfig, ensure_runtime_directories, load_config
from cs2_trend.core.logging import configure_logging, get_logger
from cs2_trend.core.run_context import RunContext
from cs2_trend.core.seed import set_global_seed

app = typer.Typer(help="CS2 Trend CLI", no_args_is_help=True, add_completion=False)
phase0_app = typer.Typer(help="Phase 0 foundation and catalog discovery commands")
phase1_app = typer.Typer(help="Phase 1 extraction commands")

app.add_typer(phase0_app, name="phase0")
app.add_typer(phase1_app, name="phase1")


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
    source: str = typer.Argument(..., help="Source to probe (example: csfloat)."),
    sample_size: int = typer.Option(1, "--sample-size", "-n", min=1),
) -> None:
    """Placeholder command for network probing and response inspection."""

    _, run_context = _get_state(ctx)
    logger = get_logger(__name__)
    logger.info(
        "phase0 probe placeholder invoked",
        extra={"run_id": run_context.run_id, "source": source, "sample_size": sample_size},
    )
    typer.echo(f"[placeholder] phase0 probe source={source} sample_size={sample_size}")


@phase0_app.command("catalog")
def phase0_catalog(
    ctx: typer.Context,
    output: Path = typer.Option(Path("data/catalog/master_catalog.json"), "--output", "-o"),
) -> None:
    """Placeholder command for canonical catalog creation from probed data."""

    _, run_context = _get_state(ctx)
    logger = get_logger(__name__)
    logger.info(
        "phase0 catalog placeholder invoked",
        extra={"run_id": run_context.run_id, "output": str(output)},
    )
    typer.echo(f"[placeholder] phase0 catalog output={output}")


@phase1_app.command("extract")
def phase1_extract(
    ctx: typer.Context,
    source: list[str] = typer.Option(None, "--source", "-s", help="Source filters."),
    limit_items: int = typer.Option(50, "--limit-items", min=1),
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
