# Project Research Summary

**Project:** CS2 Price Trend Intelligence
**Domain:** Multi-source CS2 market data platform for trend classification
**Researched:** 2026-03-25
**Confidence:** MEDIUM-HIGH

## Executive Summary

This project is a data-first intelligence pipeline, not a model-first product. Research converges on a contract-first architecture where value comes from reliable multi-market extraction (Steam, SteamDT, Buff163, CS.Money, CSFloat), canonical item identity, and auditable time-series curation before any modeling begins. Teams that build similar systems successfully separate raw ingestion from curated datasets, enforce schema quality gates, and treat source volatility (anti-bot, endpoint drift, auth expiry) as a primary engineering concern.

The recommended approach is to complete v1 as a strict Phase 0-1 delivery: (1) bootstrap a master catalog from CSFloat with stable canonical IDs, then (2) implement async source adapters behind a shared extraction kernel with probe-first endpoint discovery, retries/backoff, anomaly dumps, and minimal observability. This sequence is the shortest path to trustworthy historical tables and avoids downstream rework in preprocessing, labeling, and training.

The main risks are silent data corruption (HTML/captcha responses accepted as valid), identity mismatches across markets, temporal/price-basis misalignment, and hidden schema drift. Mitigation is explicit and practical: fail-closed contract validation, immutable raw storage, mandatory probe dumps before parser promotion, UTC normalization, explicit `price_basis`, and phase gates that block progression when data quality baselines are not met.

## Key Findings

### Recommended Stack

Research supports a Python 3.12 user-space stack optimized for AsyncIO extraction, strict typing, schema validation, and reproducible ML baselines. The strongest decisions are around operational reliability (httpx/aiohttp + tenacity + playwright for dynamic sources), data contracts (pydantic + pandera), and local analytical persistence (Parquet/pyarrow + DuckDB) with minimal infrastructure overhead.

**Core technologies:**

- **Python + uv:** Runtime and reproducible environment management in no-admin contexts.
- **httpx (+ aiohttp fallback) + tenacity:** Async extraction with resilient retry/backoff behavior.
- **playwright:** Network interception for dynamic/protected sources where HTML is non-authoritative.
- **pandas + pandera + pyarrow:** Canonical tabular processing with enforceable schema contracts.
- **duckdb:** Local analytical query engine over partitioned parquet.
- **xgboost + scikit-learn + mlflow:** Baseline modeling/evaluation stack for post-v1 phases.
- **ruff + mypy + pytest:** Required quality gates for style, typing, and tests.

### Expected Features

v1 must be judged as a data-foundation milestone (Phase 0-1), not by model metrics.

**Must have (table stakes, Phase 0-1 scope):**

- Master catalog bootstrap from CSFloat.
- Canonical item key schema (`canonical_item_id`) across all pipelines.
- Probe-first workflow per source before extractor hardening.
- Async extractors for Steam, SteamDT, Buff163, CS.Money, and CSFloat.
- Unified historical table contract (timestamp, source, price, currency, optional volume/availability).
- Retry/backoff with timestamped anomalous payload dumps.
- Basic observability (`run_id`, source/item counts, failure summaries).
- Data quality gates (schema checks, duplicate checks, minimal outlier sanity).

**Should have (differentiators if schedule allows):**

- Cross-market identity resolver refinement for edge variants.
- Source reliability scorecard (coverage/freshness/failure/schema drift).
- Checkpointed incremental extraction/backfill.
- Automated schema-drift sentinel.

**Defer (v2+ / later phases):**

- Labeling implementation details beyond extraction readiness.
- Baseline model training and tuning.
- Foundation-model inference and fine-tuning.
- Real-time trading signals/automation and full dashboard suite.

### Architecture Approach

The recommended architecture is layered and contract-first: acquisition -> curation -> ML preparation -> model. The key roadmap implication is dependency ordering: catalog and canonical identity must precede connector work; connectors must write immutable raw data before normalization; quality gates must block curated writes; only curated data should feed windowing/labeling/training.

**Major components:**

1. **`catalog_service`** — builds and refreshes canonical CS2 item universe.
1. **`source_connectors/*` + `extract_pipeline`** — fetch source-native payloads concurrently.
1. **`raw_store` + `anomaly_store`** — preserve immutable evidence for replay/debugging.
1. **`normalize_service` + `quality_gate`** — transform and validate canonical rows.
1. **`timeseries_store`** — stable downstream contract for preprocessing and modeling.

### Critical Pitfalls

1. **False-success anti-bot responses** — enforce JSON/content checks and dump invalid bodies before persistence.
1. **Endpoint/schema drift** — version per-source contracts and fail fast on mandatory-field/type/cardinality breaks.
1. **Buff163 session expiry loops** — add TTL-aware auth handling and circuit breakers on repeated auth failures.
1. **Over-aggressive concurrency/rate limiting** — apply per-host budgets, jittered backoff, and cooldown windows.
1. **Cross-market identity mismatch** — freeze canonical ID rules early and maintain versioned source mapping tables.
1. **Temporal and price-basis misalignment** — normalize to UTC and enforce a single `price_basis` with FX traceability.

## Implications for Roadmap

Based on combined research, phase ordering should follow data dependency and risk containment, not feature breadth.

### Phase 0: Catalog and Canonical Identity Foundation

**Rationale:** Every extractor and downstream join depends on stable asset identity.
**Delivers:** CSFloat catalog bootstrap, canonical ID specification, mapping table scaffolding.
**Addresses:** Table-stakes catalog bootstrap + canonical key schema.
**Avoids:** Cross-market identity mismatch and downstream join fragmentation.

### Phase 1: Multi-Source Extraction and Reliability Hardening

**Rationale:** Core v1 value is trustworthy historical data collection across sources.
**Delivers:** Async connectors, probe runner, retries/backoff, anomaly dumps, raw store, minimal telemetry.
**Addresses:** Async extraction, unified table contract input, operational observability.
**Avoids:** Anti-bot false success, auth-loop lockups, rate-limit collapse, silent endpoint drift.

### Phase 2: Normalization, Quality Gates, and Preprocessing Readiness

**Rationale:** Curated/validated time series must exist before windowing or labels.
**Delivers:** Canonical transforms, Pandera gates, UTC normalization, `price_basis` standardization, curated store.
**Uses:** pandas/pandera/pyarrow/duckdb stack decisions.
**Implements:** Curation layer boundary and fail-closed data contracts.

### Phase 3: Labeling with Leakage Controls

**Rationale:** Label quality determines model validity; leakage must be prevented by design.
**Delivers:** Forward-window labeler, threshold policy versioning, temporal split/leakage tests.
**Implements:** ML preparation layer with reproducible labeling contracts.

### Phase 4: Baseline Modeling and Evaluation

**Rationale:** Baseline only after data and labels are stable.
**Delivers:** XGBoost baseline, reproducible metrics, run tracking, initial performance benchmark.
**Uses:** xgboost/scikit-learn/mlflow stack.

### Phase Ordering Rationale

- Catalog identity precedes extraction because all source payloads must map to a stable entity key.
- Extraction reliability precedes normalization to preserve raw evidence and diagnose source volatility.
- Curation and quality gates precede labeling/training to prevent silent data poisoning.
- Modeling is intentionally delayed until data contracts are stable and leakage controls exist.

### Research Flags

Phases likely needing deeper research during planning:

- **Phase 1 (Buff163, CS.Money):** Auth/session lifecycle and endpoint volatility require source-specific operational playbooks.
- **Phase 2:** FX conversion source policy and cross-source temporal harmonization details need explicit decisions.
- **Phase 5-6 (future):** Foundation model selection and fine-tuning constraints require targeted benchmarking research.

Phases with standard patterns (can skip dedicated research-phase):

- **Phase 0:** Catalog and canonical ID governance follow well-known contract design patterns.
- **Phase 4:** XGBoost baseline training/evaluation is highly documented and low novelty.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Strong alignment with official docs and stable ecosystem tools; versions are concrete and user-space compatible. |
| Features | HIGH | Scope and boundaries are explicit in project directives and internally consistent with v1 goals. |
| Architecture | MEDIUM-HIGH | Layering and boundaries are robust; long-term scale details remain assumption-driven until load data exists. |
| Pitfalls | HIGH | Risks are concrete, domain-specific, and map directly to observable operational signals. |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **Access/compliance constraints per source:** confirm acceptable usage patterns and operational limits before aggressive extraction.
- **Throughput validation:** benchmark concurrency and storage behavior with real payload volumes before Phase 2 lock-in.
- **FX policy detail:** define authoritative conversion source and timestamp alignment rules.
- **Session operations SOP:** formalize manual/automated refresh protocol for protected sources (especially Buff163).

## Sources

### Primary (HIGH confidence)

- `.planning/research/STACK.md`
- `.planning/research/FEATURES.md`
- `.planning/research/ARCHITECTURE.md`
- `.planning/research/PITFALLS.md`
- `.planning/PROJECT.md`
- `claude.md`
- `orquestador.md`

### Secondary (MEDIUM confidence)

- https://docs.astral.sh/uv/
- https://playwright.dev/python/docs/intro
- https://docs.pydantic.dev/latest/
- https://pandera.readthedocs.io/en/stable/
- https://duckdb.org/docs/stable/

### Tertiary (LOW confidence)

- Version recency assertions from package index snapshots (PyPI JSON endpoints) that may change over time.

______________________________________________________________________

*Research completed: 2026-03-25*
*Ready for roadmap: yes*

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
