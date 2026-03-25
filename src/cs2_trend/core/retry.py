"""Retry policy utilities with progressive backoff."""

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    """Configuration for bounded retries with exponential backoff."""

    max_attempts: int = 3
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 8.0
    exponential_factor: float = 2.0
    jitter_seconds: float = 0.1


def compute_backoff_delay(
    policy: RetryPolicy,
    attempt_number: int,
    rng: random.Random | None = None,
) -> float:
    """Compute delay with exponential growth and bounded jitter.

    The `attempt_number` starts at 1 for the first retry after an initial failure.
    """

    if attempt_number < 1:
        raise ValueError("attempt_number must be >= 1")

    base_delay = policy.base_delay_seconds * (policy.exponential_factor ** (attempt_number - 1))
    bounded_delay = min(base_delay, policy.max_delay_seconds)
    jitter_source = rng if rng is not None else random
    jitter = jitter_source.uniform(0.0, policy.jitter_seconds)
    return bounded_delay + jitter


async def run_with_retry(
    operation: Callable[[], Awaitable[T]],
    policy: RetryPolicy,
    on_retry: Callable[[int, Exception, float], None] | None = None,
) -> T:
    """Execute an async operation with retries and progressive waits.

    Args:
        operation: Async callable to execute.
        policy: Retry configuration for max attempts and backoff parameters.
        on_retry: Optional callback invoked before sleeping on each retry.

    Returns:
        Result produced by `operation`.

    Raises:
        Exception: Re-raises the last operation exception after max attempts.
    """

    last_error: Exception | None = None

    for attempt in range(1, policy.max_attempts + 1):
        try:
            return await operation()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt >= policy.max_attempts:
                break

            delay = compute_backoff_delay(policy=policy, attempt_number=attempt)
            if on_retry is not None:
                on_retry(attempt, exc, delay)
            await asyncio.sleep(delay)

    if last_error is None:
        raise RuntimeError("Retry execution failed without a captured exception")

    raise last_error
