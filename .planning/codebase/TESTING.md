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
