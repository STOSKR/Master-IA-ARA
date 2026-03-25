# CONVENTIONS

## Typing and static discipline
- Project enforces mypy strict mode in pyproject.toml.
- Functions and methods consistently use explicit type hints.
- Protocols are preferred for dependency inversion (AsyncHttpClient, MarketConnector).
- TypedDict is used for serialized payload contracts in reliability modules.

## Data modeling style
- dataclasses (often slots=True, frozen=True) are used for immutable runtime records.
- pydantic models are used where richer validation/serialization is needed.
- Domain identifiers are normalized through dedicated utility functions.

## Async and concurrency patterns
- Async operations are explicit and isolated in extraction kernel and HTTP clients.
- Concurrency limits are centralized through semaphore configuration.
- Retry behavior is policy-driven (max attempts, backoff, jitter) via RetryConfig.

## Error handling conventions
- Domain-specific exceptions derive from ExtractionError.
- Error messages are actionable and include source context.
- Retry exhaustion includes metadata and optional dump path for diagnostics.
- Fallback dump logic is used to preserve raw failure evidence.

## Data quality conventions
- Price points are sanitized before persistence (finite positive price, normalized currency, UTC timestamp).
- Pandera schema validation is used for canonical history table contracts.
- Duplicate and outlier handling is deterministic and group-aware.

## Naming and formatting
- snake_case naming across modules, variables, and functions.
- Classes follow descriptive PascalCase names scoped by concern.
- Module docstrings are present in most files and describe responsibility.
- Ruff enforces import ordering and style/lint consistency.

## Determinism and reproducibility
- Random seed is set during CLI bootstrap.
- Run IDs are generated consistently and attached to logs/artifacts.
- Sorted outputs are preferred for deterministic serialization and comparisons.

## Testing conventions reflected in code
- Tests use pytest with focused scenario functions.
- Async logic is commonly wrapped with asyncio.run in tests.
- Fake HTTP clients are implemented as lightweight dataclass stubs.
- Assertions emphasize behavior and contracts, not implementation internals.

## Practical coding norms observed
- Small helper functions are used to isolate repeated normalization logic.
- IO and domain logic are separated through repositories/services boundaries.
- Constructors support explicit dependency injection for easier testing.
- Environment-based behavior is isolated at edge adapters (connectors/config).
