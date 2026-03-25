# ARCHITECTURE

## High-level pattern
- Modular monorepo-style Python project with three main package areas:
  - cs2_trend: application shell, CLI, Phase 0 domain services.
  - extraction: async connector kernel and probe-first ingestion framework.
  - cs2_price_trend: quality, reliability, and storage utilities for tabular data.
- Architecture is layered by responsibility rather than by framework.

## Primary execution entrypoints
- CLI entry in cs2_trend/cli.py with Typer subcommands phase0 and phase1.
- Python module execution entry in cs2_trend/__main__.py.
- Async extraction kernel entry in extraction/kernel.py used programmatically.

## Core data flow (implemented path)
1. Bootstrap loads config, logging, random seed, and run context.
2. phase0 probe command invokes CsfloatProbeService.
3. Probe service fetches JSON payload and stores timestamped dump.
4. phase0 catalog command parses latest dump into canonical catalog records.
5. Catalog repository writes deterministic JSON/CSV artifacts.

## Core data flow (extraction framework path)
1. AsyncExtractionKernel receives connectors and extraction targets.
2. Connector-target jobs are scheduled concurrently with semaphore limits.
3. Each connector runs probe-first fetch, parse, and cleaning pipeline.
4. Retry loop wraps each job and writes anomaly dump on exhaustion.
5. Kernel returns run metrics plus per-job success/failure envelopes.

## Abstractions and boundaries
- Protocol interfaces define integration seams:
  - AsyncHttpClient and MarketConnector in extraction/protocols.py.
  - Phase 0 repository/service interfaces in cs2_trend/phase0/interfaces.py.
- Implementations remain swappable (fake clients in tests, real clients in runtime).
- Domain normalization (canonical item ID) is isolated in cs2_trend/domain.

## Error handling architecture
- Domain-specific error hierarchy under extraction/errors.py.
- Failure metadata extraction decoupled from retry loop.
- Dump artifacts provide traceability boundary between transient failures and offline debugging.

## State and persistence model
- Runtime state is mostly ephemeral per invocation (run_id, task results).
- Persistent state is file-based: probe dumps, catalog artifacts, anomaly dumps.
- No external stateful services (DB/cache/message bus) are currently required.

## Architectural strengths
- Strong typing and protocol boundaries support testability.
- Async kernel isolates concurrency concerns from connector implementations.
- Probe-first strategy aligns with requirement to inspect payloads before final extraction logic.

## Architectural gaps
- Two partially overlapping tracks coexist (phase0 app services and extraction framework).
- Phase1 CLI orchestration is still a placeholder and does not yet call extraction kernel.
- No end-to-end command currently spans all five connectors in production flow.
