from __future__ import annotations

import asyncio
import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from cs2_trend.core.config import AppConfig
from cs2_trend.phase1.services import execute_phase1_extraction_iterative
from extraction.models import ConnectorExtraction, ExtractionTarget, PricePoint, ProbeSample


@dataclass(slots=True)
class FakeConnector:
    source_name: str = "steam"

    async def probe(self, target: ExtractionTarget) -> ProbeSample:
        return ProbeSample(
            source_name=self.source_name,
            url="https://example.test/history",
            status_code=200,
            headers={},
            body=b"{}",
        )

    async def extract(self, target: ExtractionTarget) -> ConnectorExtraction:
        sample = await self.probe(target)
        return ConnectorExtraction(
            source_name=self.source_name,
            target=target,
            sample=sample,
            points=(
                PricePoint(
                    timestamp=datetime(2026, 3, 25, 0, 0, tzinfo=UTC),
                    price=10.0,
                    volume=3,
                    currency="USD",
                ),
                PricePoint(
                    timestamp=datetime(2026, 3, 25, 1, 0, tzinfo=UTC),
                    price=10.2,
                    volume=4,
                    currency="USD",
                ),
            ),
        )


async def run_smoke() -> None:
    root = Path("data/smoke_autonomous")
    if root.exists():
        shutil.rmtree(root)
    (root / "catalog").mkdir(parents=True, exist_ok=True)

    catalog_path = root / "catalog" / "smoke_catalog.json"
    catalog_path.write_text(
        json.dumps(
            [
                {
                    "canonical_item_id": "container__alpha",
                    "market_hash_name": "Container Alpha",
                    "object_type": "container",
                },
                {
                    "canonical_item_id": "container__beta",
                    "market_hash_name": "Container Beta",
                    "object_type": "container",
                },
            ]
        ),
        encoding="utf-8",
    )

    config = AppConfig(
        data_dir=root,
        raw_dir=root / "raw",
        curated_dir=root / "curated",
        dump_dir=root / "dumps",
        probe_dump_dir=root / "dumps" / "probes",
        catalog_dir=root / "catalog",
        steam_probe_endpoint="https://example.test/history",
    )

    def factory(**_kwargs: object) -> tuple[FakeConnector, ...]:
        return (FakeConnector(),)

    result = await execute_phase1_extraction_iterative(
        config=config,
        selected_sources=["steam"],
        limit_items=2,
        catalog_path=catalog_path,
        connector_factory=factory,
        max_iterations=2,
        min_success_rate=1.0,
        min_raw_rows=2,
        max_json_rows_per_file=1,
    )

    print("run_id", result.run_id)
    print("iteration", result.iteration)
    print("quality_passed", result.quality_passed)
    print("raw_paths", len(result.raw_paths))
    print("curated_paths", len(result.curated_paths))
    print("raw_json_paths", len(result.raw_json_paths))
    print("curated_json_paths", len(result.curated_json_paths))
    print("quality_report", result.quality_report_path)


if __name__ == "__main__":
    asyncio.run(run_smoke())
