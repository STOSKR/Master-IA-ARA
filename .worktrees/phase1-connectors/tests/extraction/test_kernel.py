from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from extraction.errors import ConnectorHTTPError
from extraction.kernel import AsyncExtractionKernel, KernelConfig
from extraction.models import ConnectorExtraction, ExtractionTarget, PricePoint, ProbeSample
from extraction.retry import RetryConfig


@dataclass(slots=True)
class FlakyConnector:
    source_name: str = "flaky"
    fail_times: int = 0
    attempts: int = 0

    async def probe(self, target: ExtractionTarget) -> ProbeSample:
        return ProbeSample(
            source_name=self.source_name,
            url="https://example.local/probe",
            status_code=200,
            headers={},
            body=b"{}",
        )

    async def extract(self, target: ExtractionTarget) -> ConnectorExtraction:
        self.attempts += 1
        sample = ProbeSample(
            source_name=self.source_name,
            url="https://example.local/history",
            status_code=200,
            headers={},
            body=b'{"data":[]}',
        )

        if self.attempts <= self.fail_times:
            failing_sample = ProbeSample(
                source_name=self.source_name,
                url=sample.url,
                status_code=503,
                headers=sample.headers,
                body=b"temporary-error",
            )
            raise ConnectorHTTPError(self.source_name, failing_sample)

        return ConnectorExtraction(
            source_name=self.source_name,
            target=target,
            sample=sample,
            points=(
                PricePoint(
                    timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                    price=10.0,
                    volume=1,
                    currency="USD",
                ),
            ),
        )


def test_kernel_retries_and_reports_run_metrics(tmp_path: Path) -> None:
    async def scenario() -> None:
        target = ExtractionTarget(item_id="1", market_hash_name="AK-47 | Redline")
        connector = FlakyConnector(fail_times=1)
        kernel = AsyncExtractionKernel(
            connectors=[connector],
            config=KernelConfig(
                max_concurrency=1,
                retry=RetryConfig(
                    max_attempts=3,
                    base_delay_seconds=0.0,
                    backoff_factor=1.0,
                    max_delay_seconds=0.0,
                    jitter_seconds=0.0,
                ),
                dump_dir=tmp_path,
            ),
        )

        run_output = await kernel.run([target])

        assert run_output.metrics.run_id
        assert run_output.metrics.total_jobs == 1
        assert run_output.metrics.success_count == 1
        assert run_output.metrics.failure_count == 0

        result = run_output.results[0]
        assert result.success is True
        assert result.attempts == 2
        assert connector.attempts == 2

    asyncio.run(scenario())


def test_kernel_dumps_failure_on_retry_exhaustion(tmp_path: Path) -> None:
    async def scenario() -> str:
        target = ExtractionTarget(item_id="2", market_hash_name="AWP | Asiimov")
        connector = FlakyConnector(source_name="steam", fail_times=3)
        kernel = AsyncExtractionKernel(
            connectors=[connector],
            config=KernelConfig(
                max_concurrency=1,
                retry=RetryConfig(
                    max_attempts=2,
                    base_delay_seconds=0.0,
                    backoff_factor=1.0,
                    max_delay_seconds=0.0,
                    jitter_seconds=0.0,
                ),
                dump_dir=tmp_path,
            ),
        )

        run_output = await kernel.run([target])

        assert run_output.metrics.total_jobs == 1
        assert run_output.metrics.success_count == 0
        assert run_output.metrics.failure_count == 1

        result = run_output.results[0]
        assert result.success is False
        assert result.dump_path is not None
        return result.dump_path

    dump_path = Path(asyncio.run(scenario()))
    assert dump_path.exists()
    assert b"temporary-error" in dump_path.read_bytes()