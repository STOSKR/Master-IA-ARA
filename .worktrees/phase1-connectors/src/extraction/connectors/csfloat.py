from __future__ import annotations

import os
from collections.abc import Mapping

from extraction.connectors.base import ProbeFirstConnector
from extraction.connectors.json_parser import JsonShapeSpec, build_json_point_parser
from extraction.models import ExtractionTarget
from extraction.protocols import AsyncHttpClient


class CSFloatConnector(ProbeFirstConnector):
    """Probe-first connector for CSFloat price history APIs."""

    source_name = "csfloat"

    def __init__(
        self,
        *,
        http_client: AsyncHttpClient,
        endpoint: str | None = None,
    ) -> None:
        super().__init__(
            http_client=http_client,
            endpoint=endpoint or os.getenv("CSFLOAT_PROBE_ENDPOINT"),
            parser=build_json_point_parser(
                source_name=self.source_name,
                shapes=(
                    JsonShapeSpec(
                        points_path=("data",),
                        timestamp_field="timestamp",
                        price_field="price",
                        volume_field="volume",
                        currency_field="currency",
                        timestamp_unit="seconds",
                    ),
                    JsonShapeSpec(
                        points_path=("history",),
                        timestamp_field="timestamp",
                        price_field="price",
                        volume_field="volume",
                        currency_field="currency",
                        timestamp_unit="seconds",
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

    def build_headers(self, _target: ExtractionTarget) -> Mapping[str, str]:
        api_key = os.getenv("CSFLOAT_API_KEY")
        if not api_key:
            return {}
        return {"Authorization": api_key}