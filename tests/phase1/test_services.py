from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from cs2_trend.core.config import AppConfig
from cs2_trend.phase1.services import (
    execute_phase1_extraction,
    execute_phase1_extraction_iterative,
)
from extraction.models import (
    ConnectorExtraction,
    ExtractionTarget,
    PricePoint,
    ProbeSample,
)


@dataclass(slots=True)
class FakeSteamConnector:
    source_name: str = "steam"

    async def probe(self, target: ExtractionTarget) -> ProbeSample:
        return ProbeSample(
            source_name=self.source_name,
            url="https://example.test/steam/history",
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
                    volume=1,
                    currency="USD",
                ),
                PricePoint(
                    timestamp=datetime(2026, 3, 25, 0, 0, tzinfo=UTC),
                    price=10.0,
                    volume=1,
                    currency="USD",
                ),
                PricePoint(
                    timestamp=datetime(2026, 3, 25, 1, 0, tzinfo=UTC),
                    price=10.1,
                    volume=1,
                    currency="USD",
                ),
                PricePoint(
                    timestamp=datetime(2026, 3, 25, 2, 0, tzinfo=UTC),
                    price=10.2,
                    volume=1,
                    currency="USD",
                ),
                PricePoint(
                    timestamp=datetime(2026, 3, 25, 3, 0, tzinfo=UTC),
                    price=10.3,
                    volume=1,
                    currency="USD",
                ),
                PricePoint(
                    timestamp=datetime(2026, 3, 25, 4, 0, tzinfo=UTC),
                    price=500.0,
                    volume=1,
                    currency="USD",
                ),
            ),
        )


def test_execute_phase1_extraction_writes_raw_curated_and_metrics(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        catalog_path = tmp_path / "catalog" / "master_catalog.json"
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        catalog_path.write_text(
            json.dumps(
                [
                    {
                        "canonical_item_id": "ak_47__redline__field_tested",
                        "weapon": "AK-47",
                        "skin_name": "Redline",
                        "object_type": "weapon",
                        "source_keys": {"csfloat": "101"},
                        "metadata": {
                            "raw_market_name": "AK-47 | Redline (Field-Tested)"
                        },
                    }
                ]
            ),
            encoding="utf-8",
        )

        config = AppConfig(
            data_dir=tmp_path / "data",
            raw_dir=tmp_path / "data" / "raw",
            curated_dir=tmp_path / "data" / "curated",
            dump_dir=tmp_path / "data" / "dumps",
            probe_dump_dir=tmp_path / "data" / "dumps" / "probes",
            catalog_dir=tmp_path / "catalog",
            steam_probe_endpoint="https://example.test/steam/history",
        )

        def connector_factory(**_kwargs: object) -> tuple[FakeSteamConnector, ...]:
            return (FakeSteamConnector(),)

        result = await execute_phase1_extraction(
            config=config,
            selected_sources=["steam"],
            limit_items=1,
            catalog_path=catalog_path,
            connector_factory=connector_factory,
        )

        assert result.total_jobs == 1
        assert result.success_count == 1
        assert result.failure_count == 0
        assert result.raw_paths
        assert result.curated_paths
        assert result.raw_json_paths
        assert result.curated_json_paths
        assert result.metrics_path.exists()

        raw_frame = pd.read_csv(result.raw_paths[0])
        curated_frame = pd.read_csv(result.curated_paths[0])

        assert len(raw_frame) == 6
        assert len(curated_frame) == 5
        duplicate_rows = curated_frame[
            (curated_frame["timestamp_utc"] == "2026-03-25 00:00:00+00:00")
            & (curated_frame["price"] == 10.0)
        ]
        assert len(duplicate_rows) == 1
        assert float(curated_frame["price"].max()) < 100.0

        metrics_payload = json.loads(result.metrics_path.read_text(encoding="utf-8"))
        assert metrics_payload["sources"]["steam"]["success_count"] == 1
        assert metrics_payload["sources"]["steam"]["failure_count"] == 0

        first_raw_json = json.loads(
            result.raw_json_paths[0].read_text(encoding="utf-8")
        )
        assert isinstance(first_raw_json, list)
        assert first_raw_json
        assert first_raw_json[0]["object_type"] == "weapon"

    asyncio.run(scenario())


def test_execute_phase1_extraction_iterative_writes_quality_report(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        catalog_path = tmp_path / "catalog" / "master_catalog.json"
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        catalog_path.write_text(
            json.dumps(
                [
                    {
                        "canonical_item_id": "ak_47__redline__field_tested",
                        "market_hash_name": "AK-47 | Redline (Field-Tested)",
                        "object_type": "weapon",
                    }
                ]
            ),
            encoding="utf-8",
        )

        config = AppConfig(
            data_dir=tmp_path / "data",
            raw_dir=tmp_path / "data" / "raw",
            curated_dir=tmp_path / "data" / "curated",
            dump_dir=tmp_path / "data" / "dumps",
            probe_dump_dir=tmp_path / "data" / "dumps" / "probes",
            catalog_dir=tmp_path / "catalog",
            steam_probe_endpoint="https://example.test/steam/history",
        )

        def connector_factory(**_kwargs: object) -> tuple[FakeSteamConnector, ...]:
            return (FakeSteamConnector(),)

        result = await execute_phase1_extraction_iterative(
            config=config,
            selected_sources=["steam"],
            limit_items=1,
            catalog_path=catalog_path,
            connector_factory=connector_factory,
            max_iterations=2,
            min_success_rate=1.0,
            min_raw_rows=10,
            max_json_rows_per_file=2,
        )

        assert result.iteration == 2
        assert result.quality_passed is False
        assert result.quality_report_path is not None
        assert result.quality_report_path.exists()

        report_payload = json.loads(
            result.quality_report_path.read_text(encoding="utf-8")
        )
        assert report_payload["criteria"]["min_raw_rows"] == 10
        assert report_payload["final_passed"] is False
        assert len(report_payload["iterations"]) == 2

    asyncio.run(scenario())


def test_execute_phase1_extraction_requires_endpoint_configuration(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    async def scenario() -> None:
        monkeypatch.delenv("STEAM_PROBE_ENDPOINT", raising=False)

        catalog_path = tmp_path / "catalog" / "master_catalog.json"
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        catalog_path.write_text(
            json.dumps([{"canonical_item_id": "ak_47__redline__field_tested"}]),
            encoding="utf-8",
        )

        config = AppConfig(
            data_dir=tmp_path / "data",
            raw_dir=tmp_path / "data" / "raw",
            curated_dir=tmp_path / "data" / "curated",
            dump_dir=tmp_path / "data" / "dumps",
            probe_dump_dir=tmp_path / "data" / "dumps" / "probes",
            catalog_dir=tmp_path / "catalog",
            steam_probe_endpoint=None,
        )

        try:
            await execute_phase1_extraction(
                config=config,
                selected_sources=["steam"],
                limit_items=1,
                catalog_path=catalog_path,
            )
        except ValueError as exc:
            assert "Missing endpoint configuration" in str(exc)
        else:
            raise AssertionError(
                "Expected ValueError for missing endpoint configuration"
            )

    asyncio.run(scenario())


def test_execute_phase1_extraction_requires_csfloat_auth(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    async def scenario() -> None:
        monkeypatch.delenv("CSFLOAT_API_KEY", raising=False)
        monkeypatch.delenv("CSFLOAT_COOKIE", raising=False)

        catalog_path = tmp_path / "catalog" / "master_catalog.json"
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        catalog_path.write_text(
            json.dumps([{"canonical_item_id": "ak_47__redline__field_tested"}]),
            encoding="utf-8",
        )

        config = AppConfig(
            data_dir=tmp_path / "data",
            raw_dir=tmp_path / "data" / "raw",
            curated_dir=tmp_path / "data" / "curated",
            dump_dir=tmp_path / "data" / "dumps",
            probe_dump_dir=tmp_path / "data" / "dumps" / "probes",
            catalog_dir=tmp_path / "catalog",
            csfloat_history_endpoint="https://csfloat.com/api/v1/listings",
        )

        try:
            await execute_phase1_extraction(
                config=config,
                selected_sources=["csfloat"],
                limit_items=1,
                catalog_path=catalog_path,
            )
        except ValueError as exc:
            assert "CSFLOAT_API_KEY or CSFLOAT_COOKIE" in str(exc)
        else:
            raise AssertionError("Expected ValueError when CSFloat auth is missing")

    asyncio.run(scenario())
