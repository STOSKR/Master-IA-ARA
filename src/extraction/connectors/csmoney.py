from __future__ import annotations

import os
from collections.abc import Mapping

from extraction.connectors.base import ProbeFirstConnector
from extraction.connectors.json_parser import JsonShapeSpec, build_json_point_parser
from extraction.models import ExtractionTarget
from extraction.protocols import AsyncHttpClient


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
            endpoint=endpoint or os.getenv("CSMONEY_PROBE_ENDPOINT"),
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

    def build_query_params(self, target: ExtractionTarget) -> Mapping[str, str]:
        return {
            "name": target.market_hash_name,
            "item_id": target.item_id,
        }

    def build_headers(self, _target: ExtractionTarget) -> Mapping[str, str]:
        token = os.getenv("CSMONEY_AUTH_TOKEN")
        if not token:
            return {}
        return {"Authorization": f"Bearer {token}"}