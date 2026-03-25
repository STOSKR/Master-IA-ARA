from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from extraction.dumps import AnomalyDumper
from extraction.errors import RetryExhaustedError
from extraction.models import (
    ConnectorExtraction,
    ExtractionRun,
    ExtractionRunMetrics,
    ExtractionRunResult,
    ExtractionTarget,
)
from extraction.protocols import MarketConnector
from extraction.retry import RetryConfig, retry_with_backoff
from extraction.utils import build_failure_metadata


@dataclass(slots=True, frozen=True)
class KernelConfig:
    """Runtime configuration for async extraction orchestration."""

    max_concurrency: int = 5
    retry: RetryConfig = field(default_factory=RetryConfig)
    dump_dir: Path = Path(".dumps")


class AsyncExtractionKernel:
    """Run source connectors concurrently with bounded parallelism and retry logic."""

    def __init__(
        self,
        *,
        connectors: Sequence[MarketConnector],
        config: KernelConfig | None = None,
        anomaly_dumper: AnomalyDumper | None = None,
    ) -> None:
        self._connectors = tuple(connectors)
        self._config = config or KernelConfig()
        self._anomaly_dumper = anomaly_dumper or AnomalyDumper(base_dir=self._config.dump_dir)

    async def run(self, targets: Sequence[ExtractionTarget]) -> ExtractionRun:
        """Execute extraction for all connector-target combinations and return run metrics."""

        started_at = datetime.now(tz=UTC)
        run_id = uuid4().hex
        semaphore = asyncio.Semaphore(self._config.max_concurrency)
        tasks: list[asyncio.Task[ExtractionRunResult]] = []

        for connector in self._connectors:
            for target in targets:
                task = asyncio.create_task(self._extract_one(semaphore, connector, target))
                tasks.append(task)

        if not tasks:
            finished_at = datetime.now(tz=UTC)
            return ExtractionRun(
                metrics=ExtractionRunMetrics(
                    run_id=run_id,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_seconds=(finished_at - started_at).total_seconds(),
                    total_jobs=0,
                    success_count=0,
                    failure_count=0,
                ),
                results=(),
            )

        results = tuple(await asyncio.gather(*tasks))
        success_count = sum(1 for result in results if result.success)
        failure_count = len(results) - success_count
        finished_at = datetime.now(tz=UTC)

        return ExtractionRun(
            metrics=ExtractionRunMetrics(
                run_id=run_id,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=(finished_at - started_at).total_seconds(),
                total_jobs=len(results),
                success_count=success_count,
                failure_count=failure_count,
            ),
            results=results,
        )

    async def extract(self, targets: Sequence[ExtractionTarget]) -> list[ExtractionRunResult]:
        """Backward-compatible wrapper that returns only result entries."""

        run_output = await self.run(targets)
        return list(run_output.results)

    async def _extract_one(
        self,
        semaphore: asyncio.Semaphore,
        connector: MarketConnector,
        target: ExtractionTarget,
    ) -> ExtractionRunResult:
        attempts = 1
        started_at = datetime.now(tz=UTC)

        async def on_retry(attempt_number: int, _exc: BaseException, _delay: float) -> None:
            nonlocal attempts
            attempts = attempt_number + 1

        async def run_connector() -> ConnectorExtraction:
            async with semaphore:
                return await connector.extract(target)

        try:
            extraction = await retry_with_backoff(
                run_connector,
                config=self._config.retry,
                anomaly_dumper=self._anomaly_dumper,
                failure_metadata_extractor=lambda exc: build_failure_metadata(
                    exc=exc,
                    source_name=connector.source_name,
                    target=target,
                ),
                on_retry=on_retry,
            )
            finished_at = datetime.now(tz=UTC)
            return ExtractionRunResult(
                source_name=connector.source_name,
                target=target,
                success=True,
                attempts=attempts,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=(finished_at - started_at).total_seconds(),
                extraction=extraction,
            )
        except RetryExhaustedError as exc:
            finished_at = datetime.now(tz=UTC)
            return ExtractionRunResult(
                source_name=connector.source_name,
                target=target,
                success=False,
                attempts=exc.attempts,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=(finished_at - started_at).total_seconds(),
                error_type=type(exc.last_error).__name__,
                error_message=str(exc.last_error),
                dump_path=exc.dump_path,
            )
