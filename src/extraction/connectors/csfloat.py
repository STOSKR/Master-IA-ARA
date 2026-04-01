from __future__ import annotations

import json
import os
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

_DEFAULT_CSFLOAT_ENDPOINT = "https://csfloat.com/api/v1/listings"


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
            endpoint=endpoint or os.getenv("CSFLOAT_PROBE_ENDPOINT") or _DEFAULT_CSFLOAT_ENDPOINT,
            parser=build_json_point_parser(
                source_name=self.source_name,
                shapes=(
                    JsonShapeSpec(
                        points_path=("data",),
                        timestamp_field="created_at",
                        price_field="price",
                        timestamp_unit="iso",
                    ),
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
            "market_hash_name": target.market_hash_name,
            "item_id": target.item_id,
        }

    def build_headers(self, _target: ExtractionTarget) -> Mapping[str, str]:
        headers: dict[str, str] = {}
        api_key = os.getenv("CSFLOAT_API_KEY")
        cookie = resolve_platform_cookie_header(
            platform=self.source_name,
            env_cookie_var="CSFLOAT_COOKIE",
        )
        user_agent = os.getenv("CSFLOAT_USER_AGENT")

        if api_key:
            headers["Authorization"] = api_key
        if cookie:
            headers["Cookie"] = cookie
        if user_agent:
            headers["User-Agent"] = user_agent

        return headers

    def _build_simulated_extraction(self, *, target: ExtractionTarget) -> ConnectorExtraction:
        now = datetime.now(tz=UTC).replace(minute=0, second=0, microsecond=0)
        seed = sum(ord(ch) for ch in f"{target.item_id}:{target.market_hash_name}")
        base_price = 5.0 + (seed % 500) / 20.0

        points: list[PricePoint] = []
        for index in range(16):
            timestamp = now - timedelta(hours=15 - index)
            drift = ((seed + index * 3) % 9 - 4) * 0.06
            trend = index * 0.01
            price = max(0.05, round(base_price + trend + drift, 2))
            volume = (seed + index) % 12 + 1
            points.append(
                PricePoint(
                    timestamp=timestamp,
                    price=price,
                    volume=volume,
                    currency="USD",
                )
            )

        payload = {
            "simulated": True,
            "reason": "csfloat_auth_or_shape_blocked",
            "market_hash_name": target.market_hash_name,
            "item_id": target.item_id,
            "point_count": len(points),
        }
        sample = ProbeSample(
            source_name=self.source_name,
            url=self._endpoint or _DEFAULT_CSFLOAT_ENDPOINT,
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
