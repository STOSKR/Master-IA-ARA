from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime

from cs2_trend.phase2.bot import execute_source_constrained_extraction
from extraction.models import ConnectorExtraction, ExtractionTarget, PricePoint, ProbeSample


@dataclass(slots=True)
class TimedConnector:
    source_name: str
    work_delay_seconds: float = 0.02
    starts: list[float] = field(default_factory=list)

    async def probe(self, target: ExtractionTarget) -> ProbeSample:
        return ProbeSample(
            source_name=self.source_name,
            url=f"https://example.test/{self.source_name}",
            status_code=200,
            headers={},
            body=b"{}",
        )

    async def extract(self, target: ExtractionTarget) -> ConnectorExtraction:
        self.starts.append(asyncio.get_running_loop().time())
        await asyncio.sleep(self.work_delay_seconds)
        sample = await self.probe(target)
        return ConnectorExtraction(
            source_name=self.source_name,
            target=target,
            sample=sample,
            points=(
                PricePoint(
                    timestamp=datetime(2026, 4, 1, tzinfo=UTC),
                    price=1.0,
                    volume=1,
                    currency="USD",
                ),
            ),
        )


def test_execute_source_constrained_extraction_parallel_by_source_and_sequential_within_source() -> None:
    async def scenario() -> None:
        connectors = (
            TimedConnector(source_name="steam"),
            TimedConnector(source_name="buff163"),
        )
        targets = (
            ExtractionTarget(item_id="1", market_hash_name="Item 1"),
            ExtractionTarget(item_id="2", market_hash_name="Item 2"),
        )

        results = await execute_source_constrained_extraction(
            connectors=connectors,
            targets=targets,
            delay_seconds=0.05,
        )

        assert len(results) == 4
        assert all(result.success for result in results)

        for connector in connectors:
            assert len(connector.starts) == 2
            assert connector.starts[1] - connector.starts[0] >= 0.06

        first_call_delta = abs(connectors[0].starts[0] - connectors[1].starts[0])
        assert first_call_delta < 0.03

    asyncio.run(scenario())
