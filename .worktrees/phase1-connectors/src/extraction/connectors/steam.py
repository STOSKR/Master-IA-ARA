from __future__ import annotations

import os
from collections.abc import Mapping

from extraction.connectors.base import ProbeFirstConnector
from extraction.connectors.json_parser import JsonShapeSpec, build_json_point_parser
from extraction.models import ExtractionTarget
from extraction.protocols import AsyncHttpClient


class SteamConnector(ProbeFirstConnector):
    """Probe-first connector for Steam Community Market."""

    source_name = "steam"

    def __init__(
        self,
        *,
        http_client: AsyncHttpClient,
        endpoint: str | None = None,
    ) -> None:
        super().__init__(
            http_client=http_client,
            endpoint=endpoint or os.getenv("STEAM_PROBE_ENDPOINT"),
            parser=build_json_point_parser(
                source_name=self.source_name,
                shapes=(
                    JsonShapeSpec(
                        points_path=("prices",),
                        timestamp_field="timestamp",
                        price_field="price",
                        volume_field="volume",
                        currency_field="currency",
                        timestamp_unit="auto",
                    ),
                    JsonShapeSpec(
                        points_path=("history",),
                        timestamp_field="timestamp",
                        price_field="price",
                        volume_field="volume",
                        currency_field="currency",
                        timestamp_unit="auto",
                    ),
                ),
                default_currency="USD",
            ),
        )

    def build_query_params(self, target: ExtractionTarget) -> Mapping[str, str]:
        return {
            "market_hash_name": target.market_hash_name,
            "item_id": target.item_id,
        }
