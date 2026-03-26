# STACK

## Runtime base

- Language: Python 3.12+ (declared in pyproject.toml).
- Packaging: hatchling build backend.
- Distribution target: wheel with packages under src/cs2_trend and src/extraction.
- CLI entrypoint: cs2trend -> cs2_trend.cli:main.

## Core libraries

- httpx for async HTTP transport in extraction/http.py.
- typer for command-line interfaces in cs2_trend/cli.py.
- pydantic + pydantic-settings for typed runtime config in cs2_trend/core/config.py.
- pandas + pandera for dataframe sanitation and schema validation in cs2_price_trend/quality.

## Domain and data models

- dataclasses for extraction runtime models in extraction/models.py.
- pydantic models for canonical catalog entities in cs2_trend/domain/models.py.
- TypedDict contracts for quality and observability payloads in cs2_price_trend modules.

## Concurrency model

- asyncio used for bounded concurrent extraction in extraction/kernel.py.
- retry/backoff implemented as async utility in extraction/retry.py.
- semaphore-based max concurrency control in KernelConfig.max_concurrency.

## Transport and connector stack

- Protocol-first abstraction via extraction/protocols.py.
- Probe-first connector base class in extraction/connectors/base.py.
- Source connectors implemented for steam, steamdt, buff163, csmoney, csfloat.
- JSON shape parsing strategy via extraction/connectors/json_parser.py.

## Storage and artifact strategy

- Local filesystem persistence for probe dumps and catalog outputs in cs2_trend/phase0/repositories.py.
- Anomaly dump artifacts in extraction/dumps.py and cs2_trend/core/dumps.py.
- Partitioned path helpers in cs2_price_trend/storage/paths.py.

## Configuration system

- Environment-first settings through AppConfig (CS2TREND\_ prefix, .env support).
- Example storage path config in config/local_paths.example.toml.
- Source-specific endpoints and auth values injected by environment variables.

## Tooling and quality gates

- Ruff lint profile configured with E,F,I,B,UP,N,RUF,ASYNC rule sets.
- Mypy strict typing enabled across src and tests.
- Pytest configured with src import path and tests folder discovery.

## Observability primitives

- run_id generation and run context in cs2_trend/core/run_context.py.
- per-run metrics envelopes in extraction/models.py and cs2_price_trend/reliability/run_metrics.py.
- dump paths captured on retry exhaustion for post-mortem debugging.

## Stack maturity snapshot

- Phase 0 is functional for csfloat probing and canonical catalog generation.
- Phase 1 extraction command in CLI remains placeholder-level orchestration.
- Foundation for async multi-source extraction exists in extraction package.

## Maintenance Update 2026-03-25

- [x] Step 1 completed: duplicate/unused code cleanup and refactor in scraper-related modules.
- [x] Step 2 completed: live endpoint validation performed, blocking/auth failures reproduced, and scraper hardening applied.
- [x] Step 2 fix applied: CSFloat authentication support added via CSFLOAT_API_KEY or CSFLOAT_COOKIE in Phase 0/Phase 1 paths.
- [ ] Live extraction success against protected CSFloat endpoint remains pending until valid authentication credentials are configured.

## Next Development Steps

1. Configure CSFLOAT_API_KEY or CSFLOAT_COOKIE in runtime environment.
1. Re-run phase0 probe and phase1 extraction using authenticated session.
1. Validate persisted raw/curated outputs and metrics artifacts in data directories.
1. Continue with Phase 2 windowing implementation once authenticated extraction is stable.
