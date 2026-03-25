# CONCERNS

## 1) Phase 1 execution path is still placeholder
- Evidence: cs2_trend/cli.py phase1 extract command logs and prints placeholder output.
- Impact: users cannot run full asynchronous multi-source extraction from official CLI flow.
- Risk level: High.
- Suggested direction: wire phase1 command to extraction.AsyncExtractionKernel with connector registry and catalog-driven targets.

## 2) Split architecture can drift over time
- Evidence: both cs2_trend (phase0 app services) and extraction package implement overlapping pipeline concerns.
- Impact: duplicate logic and unclear ownership boundaries may increase maintenance cost.
- Risk level: Medium-High.
- Suggested direction: define clear boundary contract (phase0 as app layer, extraction as reusable engine) and document it.

## 3) External API fragility and auth dependencies
- Evidence: connectors rely on provider-specific payload shapes and environment-injected credentials/cookies.
- Impact: silent breakage when provider endpoints or auth flows change.
- Risk level: Medium-High.
- Suggested direction: add source-level contract tests and stronger probe diagnostics per provider.

## 4) File search noise from nested worktrees
- Evidence: repository contains .worktrees with mirrored source trees.
- Impact: broad search commands can return duplicate matches and mislead analysis/refactors.
- Risk level: Medium.
- Suggested direction: standardize search excludes for .worktrees in tooling/docs.

## 5) No CI automation detected
- Evidence: no workflow configuration observed for automated lint/type/test execution.
- Impact: quality gates depend on manual local execution.
- Risk level: Medium.
- Suggested direction: add CI pipeline running Ruff, mypy, and pytest.

## 6) Secret handling depends on runtime hygiene
- Evidence: API keys/tokens/cookies are read from environment variables and may appear in debug contexts if mishandled.
- Impact: accidental credential exposure in logs or dumps.
- Risk level: Medium.
- Suggested direction: redact sensitive headers and payload fragments in dump/log paths.

## 7) Live integration confidence is still limited
- Evidence: tests are mostly unit-level with fake HTTP clients and local file IO.
- Impact: production behavior against real providers is not continuously verified.
- Risk level: Medium.
- Suggested direction: add controlled probe-contract checks and scheduled smoke tests.

## 8) Tooling portability issue in current shell
- Evidence: ripgrep is missing in current WSL terminal environment.
- Impact: lower efficiency for fast codebase search during maintenance/debug sessions.
- Risk level: Low.
- Suggested direction: include dev environment bootstrap notes or setup script.

## Overall concern profile
- Critical blockers: none for documenting and planning.
- Highest delivery blocker for roadmap execution: phase1 extraction orchestration still not implemented.
- Immediate focus recommendation: close phase1 wiring gap before scaling preprocessing and modeling phases.
