# Architecture Patterns

**Domain:** CS2 price trend intelligence
**Researched:** 2026-03-25
**Scope:** Greenfield design optimized for Phase 0-1 first, then preprocess/label/train/infer/fine-tune

## Recommended Architecture

Layered, contract-first pipeline with strict boundaries:

1. **Acquisition Layer (Phase 0-1 now)**
   - Catalog discovery (CSFloat)
   - Source-specific async extractors (Steam, Steamdt, Buff163, CS.Money, CSFloat)
   - Raw response capture + anomaly dump pipeline
1. **Curation Layer (Phase 1 hardening, Phase 2 input)**
   - Normalization to canonical tabular schema
   - Data quality checks (Pandera)
   - Time-series persistence (partitioned datasets)
1. **ML Preparation Layer (Phase 2-3)**
   - Window builder + context enricher
   - Future-aware labeler (bullish/bearish/neutral)
1. **Model Layer (Phase 4-6)**
   - Baseline trainer (XGBoost)
   - Inference runner (foundation model + baseline)
   - Fine-tuning pipeline + comparative evaluator

### Component Boundaries

| Component | Responsibility | Inputs | Outputs | Boundary Rule |
|-----------|----------------|--------|---------|---------------|
| `catalog_service` | Build and refresh master CS2 item catalog from CSFloat | CSFloat JSON responses | Canonical catalog table | No pricing logic inside catalog component |
| `source_connectors/*` | Source auth/session management + request shaping | Catalog slice + source config | Raw source payloads | Never normalize in connector; only fetch/parse source-native shape |
| `probe_runner` | Temporary exploratory requests before final extractor logic | Endpoint candidates | Probe dumps + endpoint map | Must run before promoting extractor changes |
| `extract_pipeline` | Concurrent async extraction orchestration | Catalog + connector clients | Raw history batches | No schema coercion beyond minimal transport parsing |
| `raw_store` | Immutable raw payload storage with timestamps | Raw payloads + metadata | Versioned raw files | Append-only; no mutation |
| `anomaly_store` | Persist repeated failures and unexpected bodies | Failed responses | Timestamped dump files | Always write full body + request context |
| `normalize_service` | Convert source payloads into canonical time-series rows | Raw payloads | Canonical price rows | Source-specific transforms isolated per adapter |
| `quality_gate` | Enforce schema and invariants | Canonical rows | Validated rows + rejection reports | Block downstream writes on schema failure |
| `timeseries_store` | Durable curated storage for downstream phases | Validated rows | Partitioned tables/files | Read interface stable for ML phases |
| `dataset_builder` (future) | Build training-ready windows/context datasets | Curated time-series + context tables | Window datasets | Cannot call connectors directly |
| `labeling_service` (future) | Apply forward-window labeling policy | Window datasets + thresholds | Labeled datasets | Label rules versioned and reproducible |
| `training_service` (future) | Train/evaluate baseline models | Labeled datasets | Model artifacts + metrics | Pure consumer; no extraction responsibility |
| `inference_service` (future) | Score latest windows with selected model | Feature windows + model artifacts | Trend predictions | Read-only access to curated stores |
| `finetune_service` (future) | Fine-tune foundation models + compare results | Curated/labeled datasets + base models | Tuned checkpoints + benchmark report | Isolated runtime profile from extraction jobs |

## Data Flow

`CSFloat catalog probe` -> `catalog_service` -> `catalog table`

`catalog table` -> `extract_pipeline` -> `source_connectors/*`

`source_connectors/*` -> `raw_store`

`source_connectors/* failures` -> `retry/backoff policy` -> (`success` -> `raw_store`, `exhausted` -> `anomaly_store`)

`raw_store` -> `normalize_service` -> `quality_gate` -> `timeseries_store`

Future extension:

`timeseries_store` -> `dataset_builder` -> `labeling_service` -> `training_service` -> `model_registry` -> `inference_service`

`timeseries_store + labeled datasets + model outputs` -> `finetune_service` -> `comparison reports`

## Build Order (with dependency rationale)

1. **Foundation runtime (shared config + logging + retries + path policy)**
   - Needed first because every component must obey user-space, reproducibility, and failure-dump rules.
1. **Phase 0: `catalog_service` + probe workflow for CSFloat**
   - Required dependency for all extractors; creates the object universe and identifiers.
1. **Shared extraction kernel (`source_connector` interface + `extract_pipeline`)**
   - Prevents five monolithic scripts and enforces a uniform async contract.
1. **Per-source adapters (Steam, Steamdt, Buff163, CS.Money, CSFloat)**
   - Implemented behind same interface; each can evolve without touching orchestration.
1. **Raw/anomaly stores + operational telemetry**
   - Needed early for debugging anti-bot issues and unknown payload shapes.
1. **Normalization + quality gate + curated `timeseries_store`**
   - Completes Phase 1 deliverable and provides stable input for Phase 2+.
1. **Future-ready read contracts (`dataset_builder` input API)**
   - Add now as interface skeleton to avoid later breaking changes.

## User-Space / No-Admin Constraints (Design Implications)

- Use project-local paths only (for example: `.data/raw`, `.data/curated`, `.data/dumps`, `.artifacts/models`).
- Prefer file/embedded engines that run without system services (Parquet + DuckDB/SQLite) for v1.
- Keep scheduling user-level (CLI entrypoints, cron/task scheduler in user context), not daemon/service installs.
- Keep secrets in user-space config (`.env` + per-source session files), never OS-level privileged stores.
- Isolate optional heavy ML dependencies by phase so Phase 0-1 can run on minimal local environment.

## Patterns to Follow

### Pattern 1: Source Adapter + Canonical Contract

**What:** Each market source implements a strict adapter interface; canonical schema lives outside adapters.
**When:** Always, including exploratory/probe code promotion.
**Why:** Keeps source volatility isolated and protects downstream preprocess/label/train modules.

### Pattern 2: Bronze/Silver Separation

**What:** Keep immutable raw payloads (bronze) separate from validated canonical time-series (silver).
**When:** From first extraction run onward.
**Why:** Enables replay, auditability, and parser evolution without re-scraping.

### Pattern 3: Fail-Closed Quality Gate

**What:** Data moves downstream only after schema validation and timestamp/value checks.
**When:** Before writing curated time-series.
**Why:** Prevents silent model drift caused by malformed upstream payloads.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Monolithic extractor scripts

**Why bad:** Coupled logic, hard debugging, no per-source isolation.
**Instead:** Shared extraction kernel + source adapters.

### Anti-Pattern 2: Direct connector-to-training coupling

**Why bad:** Future phases become fragile and non-reproducible.
**Instead:** Force all consumers through curated store contracts.

### Anti-Pattern 3: Skipping probe dumps on unknown payloads

**Why bad:** Hidden parse assumptions and brittle fixes.
**Instead:** Mandatory probe + raw dump before parser updates.

## Scalability Considerations

| Concern | At 100 assets | At 10K assets | At 1M observations/day |
|---------|---------------|---------------|-------------------------|
| Extraction concurrency | Single process async | Bounded worker pools per source | Source-partitioned jobs + backpressure |
| Storage | Local Parquet | Partitioned Parquet + DuckDB indexes | Object storage layout + compacted partitions |
| Validation cost | Inline validation | Batch validation per partition | Incremental validation + sampled deep checks |
| Training cadence | Manual runs | Scheduled baseline retrains | Feature/versioned pipelines + model registry gating |

## Sources

- Internal project constraints: `.planning/PROJECT.md`
- Domain and phase directives: `claude.md`
- Orchestration and operational rules: `orquestador.md`

## Confidence

**Overall:** MEDIUM-HIGH

- High confidence on Phase 0-1 boundaries and operational constraints (explicitly defined in project docs).
- Medium confidence on long-term scaling details (designed to be compatible with stated future phases, not yet validated by real throughput metrics).

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
