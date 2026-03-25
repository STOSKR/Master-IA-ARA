from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from extraction.dumps import AnomalyDumpContext, AnomalyDumper
from extraction.errors import RetryExhaustedError, RetryFailureMetadata

RetryHandler = Callable[[int, BaseException, float], Awaitable[None] | None]
FailureMetadataExtractor = Callable[[BaseException], RetryFailureMetadata | None]


@dataclass(slots=True, frozen=True)
class RetryConfig:
    """Config for bounded retry/backoff behavior."""

    max_attempts: int = 3
    base_delay_seconds: float = 0.5
    backoff_factor: float = 2.0
    max_delay_seconds: float = 8.0
    jitter_seconds: float = 0.0


async def retry_with_backoff[T](
    operation: Callable[[], Awaitable[T]],
    *,
    config: RetryConfig,
    retry_exceptions: tuple[type[BaseException], ...] = (Exception,),
    anomaly_dumper: AnomalyDumper | None = None,
    failure_metadata_extractor: FailureMetadataExtractor | None = None,
    on_retry: RetryHandler | None = None,
) -> T:
    """Execute an async operation with exponential backoff and optional dump on final failure."""

    attempt = 1
    while True:
        try:
            return await operation()
        except retry_exceptions as exc:
            if attempt >= config.max_attempts:
                dump_path = None
                if anomaly_dumper is not None:
                    dump_path = _dump_failure(
                        anomaly_dumper=anomaly_dumper,
                        metadata=(
                            failure_metadata_extractor(exc)
                            if failure_metadata_extractor is not None
                            else None
                        ),
                        attempt=attempt,
                    )
                raise RetryExhaustedError(
                    attempts=attempt,
                    last_error=exc,
                    dump_path=dump_path,
                ) from exc

            delay = min(
                config.base_delay_seconds * (config.backoff_factor ** (attempt - 1)),
                config.max_delay_seconds,
            )
            if config.jitter_seconds > 0:
                delay += random.uniform(0.0, config.jitter_seconds)

            if on_retry is not None:
                maybe_awaitable = on_retry(attempt, exc, delay)
                if isinstance(maybe_awaitable, Awaitable):
                    await maybe_awaitable

            await asyncio.sleep(delay)
            attempt += 1


def _dump_failure(
    *,
    anomaly_dumper: AnomalyDumper,
    metadata: RetryFailureMetadata | None,
    attempt: int,
) -> str:
    if metadata is None:
        context = AnomalyDumpContext(
            source_name="unknown-source",
            item_id="unknown-item",
            reason="retry-exhausted-without-metadata",
            attempt=attempt,
        )
        return str(anomaly_dumper.dump_raw_failure(raw_body=None, context=context))

    context = AnomalyDumpContext(
        source_name=metadata.source_name,
        item_id=metadata.item_id,
        reason=metadata.reason,
        attempt=attempt,
        response_status=metadata.response_status,
        response_url=metadata.response_url,
    )
    return str(anomaly_dumper.dump_raw_failure(raw_body=metadata.raw_body, context=context))
