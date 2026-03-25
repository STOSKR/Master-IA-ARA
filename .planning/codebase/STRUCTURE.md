# STRUCTURE

## Repository layout
- config/: local configuration examples.
- src/: all Python packages.
- tests/: pytest suite organized by concern.
- .planning/: roadmap and workflow artifacts.
- .worktrees/: parallel workspace copies for phase branches.

## Source package map
- src/cs2_trend/
  - core/: config, logging, retry policy, run context, seed/time/path helpers.
  - domain/: canonical IDs and domain models.
  - phase0/: interfaces, models, repositories, services, HTTP clients.
  - cli.py and __main__.py as application entrypoints.
- src/extraction/
  - connectors/: source-specific connectors + parser helpers + base class.
  - kernel.py: async orchestration and run metrics aggregation.
  - retry.py/errors.py/dumps.py/http.py: reliability and transport primitives.
  - models.py/protocols.py: core contracts.
- src/cs2_price_trend/
  - quality/: dataframe contract, sanitation, validation, frame helpers.
  - reliability/: run-level metrics utilities.
  - storage/: partition and directory path helpers.

## Tests layout
- tests/extraction/: kernel and connector probe-first behavior tests.
- tests/quality/: validation and sanitation tests around Pandera and outlier logic.
- tests/reliability/: run metrics behavior and normalization checks.
- tests/storage/: partition path and directory creation tests.
- tests root-level files: canonical ID, catalog service, probe repository tests.

## Naming and module conventions
- snake_case files and functions across project.
- Connector classes follow SourceConnector pattern (SteamConnector, CSFloatConnector).
- Most modules include focused docstrings and small helper functions.

## Data artifact paths
- Runtime directories initialized under configurable data root paths.
- Probe dumps and catalog output under cs2_trend core config directories.
- Extraction anomaly dumps default to .dumps unless overridden.

## Worktree considerations
- .worktrees contains alternate phase workspaces that mirror src paths.
- Workspace-wide searches may include .worktrees content unless excluded.
- Codebase mapping in this folder targets the main repository root, not nested worktrees.

## Structural maturity snapshot
- Foundation modules are already decomposed by responsibility.
- Clear separation exists between domain logic, infrastructure, and orchestration.
- Future consolidation is needed to avoid drift between cs2_trend phase flow and extraction package flow.

## Maintenance Update 2026-03-25
- [x] Step 1 completed: duplicate/unused code cleanup and refactor in scraper-related modules.
- [x] Step 2 completed: live endpoint validation performed, blocking/auth failures reproduced, and scraper hardening applied.
- [x] Step 2 fix applied: CSFloat authentication support added via CSFLOAT_API_KEY or CSFLOAT_COOKIE in Phase 0/Phase 1 paths.
- [ ] Live extraction success against protected CSFloat endpoint remains pending until valid authentication credentials are configured.

## Next Development Steps
1. Configure CSFLOAT_API_KEY or CSFLOAT_COOKIE in runtime environment.
2. Re-run phase0 probe and phase1 extraction using authenticated session.
3. Validate persisted raw/curated outputs and metrics artifacts in data directories.
4. Continue with Phase 2 windowing implementation once authenticated extraction is stable.
