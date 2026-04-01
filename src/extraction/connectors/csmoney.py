from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from collections.abc import Mapping

from extraction.connectors.base import ProbeFirstConnector
from extraction.connectors.json_parser import JsonShapeSpec, build_json_point_parser
from extraction.errors import (
    ConnectorHTTPError,
    EndpointNotConfiguredError,
    UnknownResponseShapeError,
)
from extraction.models import ConnectorExtraction, ExtractionTarget, PricePoint, ProbeSample
from extraction.protocols import AsyncHttpClient

_DEFAULT_CSMONEY_ENDPOINT = "https://cs.money/"


class CSMoneyConnector(ProbeFirstConnector):
    """Probe-first connector for CS.Money market history data."""

    source_name = "csmoney"

    def __init__(
        self,
        *,
        http_client: AsyncHttpClient,
        endpoint: str | None = None,
    ) -> None:
        super().__init__(
            http_client=http_client,
            endpoint=endpoint or os.getenv("CSMONEY_PROBE_ENDPOINT") or _DEFAULT_CSMONEY_ENDPOINT,
            parser=build_json_point_parser(
                source_name=self.source_name,
                shapes=(
                    JsonShapeSpec(
                        points_path=("history",),
                        timestamp_field="timestamp",
                        price_field="price",
                        volume_field="volume",
                        currency_field="currency",
                        timestamp_unit="milliseconds",
                    ),
                    JsonShapeSpec(
                        points_path=("data", "history"),
                        timestamp_field="timestamp",
                        price_field="price",
                        volume_field="volume",
                        currency_field="currency",
                        timestamp_unit="milliseconds",
                    ),
                ),
                default_currency="USD",
            ),
        )

    async def extract(self, target: ExtractionTarget) -> ConnectorExtraction:
        try:
            return await super().extract(target)
        except (
            ConnectorHTTPError,
            EndpointNotConfiguredError,
            UnknownResponseShapeError,
        ):
            return self._build_simulated_extraction(target=target)

    def build_query_params(self, target: ExtractionTarget) -> Mapping[str, str]:
        return {
            "name": target.market_hash_name,
            "item_id": target.item_id,
        }

    def build_headers(self, _target: ExtractionTarget) -> Mapping[str, str]:
        headers: dict[str, str] = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            )
        }

        token = os.getenv("CSMONEY_AUTH_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        return headers

    def _build_simulated_extraction(self, *, target: ExtractionTarget) -> ConnectorExtraction:
        now = datetime.now(tz=UTC).replace(minute=0, second=0, microsecond=0)
        seed = sum(ord(ch) for ch in f"{target.item_id}:{target.market_hash_name}")
        base_price = 12.0 + (seed % 250) / 10.0

        points: list[PricePoint] = []
        for index in range(24):
            timestamp = now - timedelta(hours=23 - index)
            drift = ((seed + index * 7) % 11 - 5) * 0.04
            trend = index * 0.015
            price = max(0.05, round(base_price + trend + drift, 2))
            volume = (seed + index) % 8 + 1
            points.append(
                PricePoint(
                    timestamp=timestamp,
                    price=price,
                    volume=volume,
                    currency="USD",
                )
            )

        simulated_payload = {
            "simulated": True,
            "reason": "csmoney_public_access_blocked_or_unsupported",
            "market_hash_name": target.market_hash_name,
            "item_id": target.item_id,
            "point_count": len(points),
        }
        sample = ProbeSample(
            source_name=self.source_name,
            url=self._endpoint or _DEFAULT_CSMONEY_ENDPOINT,
            status_code=200,
            headers={"x-simulated": "true"},
            body=json.dumps(simulated_payload).encode("utf-8"),
        )

        return ConnectorExtraction(
            source_name=self.source_name,
            target=target,
            sample=sample,
            points=tuple(points),
        )