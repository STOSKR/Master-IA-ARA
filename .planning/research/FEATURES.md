# Feature Landscape

**Domain:** Internal CS2 skin market trend analysis/prediction platform  
**Researched:** 2026-03-25  
**Scope focus:** v1 limited to Phase 0-1 (master catalog + price history extraction)

## v1 Boundaries (Realistic)

- **In scope:** catalog creation, multi-market extraction, normalization, reliability, and data quality controls needed to produce trustworthy historical tables.
- **Out of scope for v1:** labeling logic, model training, model serving, and strategy/decision automation.

## Table Stakes

Features expected for a usable internal data foundation. Missing these blocks Phase 2+.

| Feature | Why Expected | Complexity | Dependencies | v1 Boundary Note |
|---------|--------------|------------|--------------|------------------|
| Master catalog bootstrap from CSFloat (weapon, skin, wear, special attrs) | Required to define extraction universe and avoid ad-hoc item selection | Medium | CSFloat API/network inspection; local persistence | Must ship in Phase 0 |
| Canonical item key schema (stable IDs across all pipelines) | Prevents downstream join failures and duplicated entities | Medium | Catalog bootstrap | Must ship in Phase 0 |
| Async extractors for Steam, SteamDT, Buff163, CS.Money, CSFloat | Core requirement to collect historical prices at scale | High | Catalog + per-source endpoint discovery | Phase 1 core deliverable |
| Pre-parser inspection workflow (raw sample capture before final parse) | Avoids false assumptions about payload structure | Medium | Per-source connectivity | Mandatory guardrail in every connector |
| Unified historical table contract (timestamp, source, price, volume/availability when present, currency) | Enables comparable time-series across sources | Medium | Canonical keys + extractor outputs | v1 can keep nullable optional fields |
| Retry/backoff + anomalous payload dumps with timestamp | Essential for resilience and reproducible debugging | Medium | Storage path + logging | Must be default behavior |
| Basic extraction observability (run_id, counts, failures by source/item) | Needed to trust data completeness and triage failures fast | Low-Medium | Logging around extractors | CLI/log-file level is enough for v1 |
| Data quality gates (schema checks, duplicate checks, minimal outlier sanity) | Prevents polluted historical dataset entering preprocessing | Medium | Unified table contract | Keep rules simple and explicit in v1 |

## Differentiators (High-Value in v1 if capacity allows)

These are not strictly required to start, but materially improve reliability and downstream velocity.

| Feature | Value Proposition | Complexity | Dependencies | Suggested Timing |
|---------|-------------------|------------|--------------|------------------|
| Cross-market identity resolver (same skin across marketplaces, wear variants normalized) | Reduces manual mapping debt before modeling phases | High | Canonical key schema + catalog enrichment | Late Phase 1 / Phase 1.1 |
| Source reliability scorecard (coverage %, freshness lag, failure rate, schema drift incidents) | Makes data trust measurable and guides connector hardening | Medium | Observability + quality gates | End of Phase 1 |
| Checkpointed incremental extraction (resume/backfill windows deterministically) | Cuts rerun cost and enables controlled reprocessing | Medium-High | Unified table + run metadata | End of Phase 1 |
| Automated schema-drift sentinel per source | Detects silent breakage early when APIs/web payloads change | Medium | Raw sample archive + expected schema fingerprints | Phase 1.1 |

## Anti-Features (Do Not Build in v1)

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Model training/evaluation (XGBoost/foundation models) in same milestone | Expands scope before data layer is trustworthy | Freeze at extraction readiness; defer to Phase 4+ |
| Real-time trading signals or execution automation | High operational/compliance risk; not required for data foundation | Focus on historical data correctness and reproducibility |
| Full product UI/dashboard suite | Frontend work can hide unresolved data quality issues | Use concise logs + lightweight internal reports |
| Aggressive anti-bot bypass engineering for protected sources | High fragility and maintenance burden in v1 | Implement compliant access patterns and explicit failure surfacing |
| Over-engineered feature store before stable schemas | Premature architecture likely to be rewritten | Keep normalized tabular datasets + versioned contracts |

## Feature Dependencies

```text
CSFloat catalog bootstrap
  -> Canonical item key schema
    -> Per-source endpoint discovery + raw sample inspection
      -> Async extractors (5 sources)
        -> Unified historical table contract
          -> Data quality gates
            -> Extraction readiness for Phase 2+

Observability + retry/backoff + anomalous dumps
  -> Reliable operations + faster connector hardening
```

## MVP Recommendation (Phase 0-1)

Prioritize in this exact order:

1. Master catalog bootstrap + canonical keys.
2. Raw sample inspection workflow per source.
3. Async multi-source extractors producing unified historical tables.
4. Retry/backoff, dumps, and minimal observability.
5. Basic schema/quality gates.

Defer unless schedule is ahead:

- Cross-market identity resolver.
- Reliability scorecard and schema-drift sentinel.
- Checkpointed incremental backfill.

## Sources

- `c:\Master-IA-ARA\.planning\PROJECT.md`
- `c:\Master-IA-ARA\claude.md`
- `c:\Master-IA-ARA\orquestador.md`