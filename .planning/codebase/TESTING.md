# TESTING

## Framework and configuration
- Test runner: pytest (configured in pyproject.toml).
- Discovery root: tests/.
- Import path: src is injected via pytest pythonpath setting.
- Static analysis stack alongside tests: mypy strict and Ruff lint.

## Test organization by concern
- tests/extraction/ validates async kernel, retries, connector probe-first behavior.
- tests/quality/ validates Pandera schema constraints and sanitation logic.
- tests/reliability/ validates run metrics counting and normalization.
- tests/storage/ validates path partitioning and directory creation behavior.
- root-level tests validate canonical ID building and phase0 repository/service flows.

## Covered behavior highlights
- Kernel metrics and retry behavior including failure dump persistence.
- Connector behavior on missing endpoint, happy-path parsing, and unknown shapes.
- Canonical ID determinism across formatting variants.
- Catalog parsing and JSON/CSV persistence from probe dumps.
- Data quality checks for required columns, source/currency/price_basis validity.
- Outlier detection/sanitization and duplicate handling determinism.

## Test style patterns
- Arrange-Act-Assert style with compact fixtures/helpers.
- Temporary filesystem usage through tmp_path for repository/storage tests.
- Fake adapter implementations for HTTP boundaries to avoid real network calls.
- Explicit exception assertions using pytest.raises with message matching.

## Gaps and missing coverage
- No end-to-end CLI integration tests for phase0 and phase1 commands.
- No live or contract tests against external provider APIs.
- No property-based tests for parser robustness against malformed payloads.
- No performance/load tests for large connector-target matrices.
- No CI workflow files detected to enforce automated checks on push/PR.

## Confidence summary
- Unit-level confidence is good for current foundations.
- Probe-first extraction core has meaningful behavioral coverage.
- Quality/storage/reliability helpers are well exercised for normal and edge cases.
- Integration confidence across full multi-source workflow remains limited until phase1 wiring is complete.

## Recommended next test increments
- Add CLI command tests using Typer test runner and controlled fixture directories.
- Add integration test that runs AsyncExtractionKernel with multiple connectors and mixed outcomes.
- Add parser contract snapshots per source payload shape.
- Add a CI pipeline to run Ruff, mypy, and pytest on every change.

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
