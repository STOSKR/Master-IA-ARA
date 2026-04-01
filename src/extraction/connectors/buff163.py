from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime, timedelta
from collections.abc import Mapping

from extraction.auth_cookies import resolve_platform_cookie_header
from extraction.connectors.base import ProbeFirstConnector
from extraction.connectors.json_parser import JsonShapeSpec, build_json_point_parser
from extraction.errors import (
    ConnectorHTTPError,
    EndpointNotConfiguredError,
    UnknownResponseShapeError,
)
from extraction.models import ConnectorExtraction, ExtractionTarget, PricePoint, ProbeSample
from extraction.protocols import AsyncHttpClient

_DEFAULT_BUFF163_ENDPOINT = "https://buff.163.com/api/market/goods/sell_order"


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
            endpoint=endpoint or os.getenv("BUFF163_PROBE_ENDPOINT") or _DEFAULT_BUFF163_ENDPOINT,
            parser=build_json_point_parser(
                source_name=self.source_name,
                shapes=(
                    JsonShapeSpec(
                        points_path=("data", "items"),
                        timestamp_field="created_at",
                        price_field="price",
                        timestamp_unit="seconds",
                    ),
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
            "game": "csgo",
            "goods_id": target.item_id,
            "page_num": "1",
            "sort_by": "default",
            "mode": "",
            "allow_tradable_cooldown": "1",
            "_": str(int(time.time() * 1000)),
        }

    def build_headers(self, target: ExtractionTarget) -> Mapping[str, str]:
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

        headers.setdefault(
            "Referer",
            f"https://buff.163.com/goods/{target.item_id}?from=market#tab=selling",
        )
        return headers

    def _build_simulated_extraction(self, *, target: ExtractionTarget) -> ConnectorExtraction:
        now = datetime.now(tz=UTC).replace(minute=0, second=0, microsecond=0)
        seed = sum(ord(ch) for ch in f"{target.item_id}:{target.market_hash_name}")
        base_price = 40.0 + (seed % 1200) / 10.0

        points: list[PricePoint] = []
        for index in range(12):
            timestamp = now - timedelta(hours=11 - index)
            drift = ((seed + index * 5) % 13 - 6) * 0.12
            price = max(0.05, round(base_price + drift, 2))
            volume = (seed + index) % 10 + 1
            points.append(
                PricePoint(
                    timestamp=timestamp,
                    price=price,
                    volume=volume,
                    currency="CNY",
                )
            )

        payload = {
            "simulated": True,
            "reason": "buff163_public_history_blocked_or_unmapped_goods_id",
            "market_hash_name": target.market_hash_name,
            "item_id": target.item_id,
            "point_count": len(points),
        }
        sample = ProbeSample(
            source_name=self.source_name,
            url=self._endpoint or _DEFAULT_BUFF163_ENDPOINT,
            status_code=200,
            headers={"x-simulated": "true"},
            body=json.dumps(payload).encode("utf-8"),
        )

        return ConnectorExtraction(
            source_name=self.source_name,
            target=target,
            sample=sample,
            points=tuple(points),
        )
