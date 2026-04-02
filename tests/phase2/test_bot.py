from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from cs2_trend.phase2.bot import (
    _write_rows_json_shards,
    execute_source_constrained_extraction,
)
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


def test_write_rows_json_shards_emits_compact_item_series_payload(tmp_path: Path) -> None:
    rows = [
        {
            "timestamp_utc": "2026-04-02T00:00:00+00:00",
            "source": "steam",
            "canonical_item_id": "agent__alpha",
            "item_name": "Agent Alpha",
            "price": 10.0,
            "currency": "USD",
            "price_basis": "listing",
            "volume": 3.0,
            "availability": None,
            "object_type": "agent",
            "object_subtype": None,
            "type_name": None,
        },
        {
            "timestamp_utc": "2026-04-02T01:00:00+00:00",
            "source": "steam",
            "canonical_item_id": "agent__alpha",
            "item_name": "Agent Alpha",
            "price": 11.0,
            "currency": "USD",
            "price_basis": "listing",
            "volume": 4.0,
            "availability": None,
            "object_type": "agent",
            "object_subtype": None,
            "type_name": None,
        },
        {
            "timestamp_utc": "2026-04-02T00:00:00+00:00",
            "source": "steam",
            "canonical_item_id": "agent__beta",
            "item_name": "Agent Beta",
            "price": 8.0,
            "currency": "USD",
            "price_basis": "listing",
            "volume": 2.0,
            "availability": None,
            "object_type": "agent",
            "object_subtype": None,
            "type_name": None,
        },
    ]

    output_paths = _write_rows_json_shards(
        rows=rows,
        root_dir=tmp_path,
        run_id="run-test",
        timestamp=datetime(2026, 4, 2, tzinfo=UTC),
        curated=True,
        max_rows_per_file=2,
    )

    assert len(output_paths) == 2

    first_payload = json.loads(output_paths[0].read_text(encoding="utf-8"))
    second_payload = json.loads(output_paths[1].read_text(encoding="utf-8"))

    assert first_payload["source"] == "steam"
    assert first_payload["category"] == "agent"
    assert first_payload["kind"] == "curated"
    assert first_payload["item_count"] == 1
    assert first_payload["point_count"] == 2
    assert first_payload["items"][0]["name"] == "Agent Alpha"
    assert len(first_payload["items"][0]["series"]) == 2

    assert second_payload["item_count"] == 1
    assert second_payload["point_count"] == 1
    assert second_payload["items"][0]["name"] == "Agent Beta"
