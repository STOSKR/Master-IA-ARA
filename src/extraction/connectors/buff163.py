from __future__ import annotations

import os
from collections.abc import Mapping

from extraction.auth_cookies import resolve_platform_cookie_header
from extraction.connectors.base import ProbeFirstConnector
from extraction.connectors.json_parser import JsonShapeSpec, build_json_point_parser
from extraction.models import ExtractionTarget
from extraction.protocols import AsyncHttpClient


class Buff163Connector(ProbeFirstConnector):
    """Probe-first connector for Buff163 historical price payloads."""

    source_name = "buff163"

    def __init__(
        self,
        *,
        http_client: AsyncHttpClient,
        endpoint: str | None = None,
    ) -> None:
        super().__init__(
            http_client=http_client,
            endpoint=endpoint or os.getenv("BUFF163_PROBE_ENDPOINT"),
            parser=build_json_point_parser(
                source_name=self.source_name,
                shapes=(
                    JsonShapeSpec(
                        points_path=("data", "items"),
                        timestamp_field="timestamp",
                        price_field="price",
                        volume_field="volume",
                        currency_field="currency",
                        timestamp_unit="milliseconds",
                    ),
                    JsonShapeSpec(
                        points_path=("items",),
                        timestamp_field="timestamp",
                        price_field="price",
                        volume_field="volume",
                        currency_field="currency",
                        timestamp_unit="milliseconds",
                    ),
                ),
                default_currency="CNY",
            ),
        )

    def build_query_params(self, target: ExtractionTarget) -> Mapping[str, str]:
        return {
            "goods_id": target.item_id,
            "market_hash_name": target.market_hash_name,
        }

    def build_headers(self, _target: ExtractionTarget) -> Mapping[str, str]:
        headers: dict[str, str] = {}
        cookie = resolve_platform_cookie_header(
            platform=self.source_name,
            env_cookie_var="BUFF163_COOKIE",
        )
        user_agent = os.getenv("BUFF163_USER_AGENT")
        if cookie:
            headers["Cookie"] = cookie
        if user_agent:
            headers["User-Agent"] = user_agent
        return headers
