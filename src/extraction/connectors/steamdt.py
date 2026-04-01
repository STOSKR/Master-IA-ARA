from __future__ import annotations

import json
import os
import time
from collections.abc import Mapping
from typing import Any

from extraction.connectors.base import ProbeFirstConnector
from extraction.connectors.json_parser import JsonShapeSpec, build_json_point_parser
from extraction.errors import UnknownResponseShapeError
from extraction.models import ExtractionTarget, PricePoint, ProbeSample
from extraction.protocols import AsyncHttpClient

_DEFAULT_STEAMDT_ENDPOINT = "https://api.steamdt.com/index/item-block/v1/summary"


class SteamdtConnector(ProbeFirstConnector):
    """Probe-first connector for SteamDT market history."""

    source_name = "steamdt"

    def __init__(
        self,
        *,
        http_client: AsyncHttpClient,
        endpoint: str | None = None,
    ) -> None:
        json_parser = build_json_point_parser(
            source_name=self.source_name,
            shapes=(
                JsonShapeSpec(
                    points_path=("data", "history"),
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
        )

        def parse_with_fallback(
            sample: ProbeSample,
            target: ExtractionTarget,
        ) -> tuple[PricePoint, ...]:
            try:
                return json_parser(sample, target)
            except UnknownResponseShapeError:
                return _parse_summary_index_points(sample=sample)

        super().__init__(
            http_client=http_client,
            endpoint=endpoint or os.getenv("STEAMDT_PROBE_ENDPOINT") or _DEFAULT_STEAMDT_ENDPOINT,
            parser=parse_with_fallback,
        )

    def build_query_params(self, target: ExtractionTarget) -> Mapping[str, str]:
        if self._endpoint and "market-comparsion" in self._endpoint:
            return {
                "itemId": target.item_id,
                "platform": "ALL",
                "typeDay": "1",
                "dateType": "3",
                "timestamp": str(int(time.time() * 1000)),
            }

        return {
            "timestamp": str(int(time.time() * 1000)),
        }


def _parse_summary_index_points(*, sample: ProbeSample) -> tuple[PricePoint, ...]:
    payload = _decode_json(sample)
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise ValueError("missing data object")

    hot = data.get("hot")
    if not isinstance(hot, Mapping):
        raise ValueError("missing hot object")

    rows = hot.get("defaultList")
    if not isinstance(rows, list) or not rows:
        raise ValueError("missing defaultList rows")

    points: list[PricePoint] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue

        raw_price = row.get("index")
        price = _coerce_float(raw_price)
        if price is None:
            continue

        points.append(
            PricePoint(
                timestamp=sample.captured_at,
                price=price,
                volume=None,
                currency="CNY",
            )
        )

    if not points:
        raise ValueError("no index rows parsed")

    return tuple(points)


def _decode_json(sample: ProbeSample) -> dict[str, Any]:
    payload = json.loads(sample.body.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    return payload


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        normalized = value.replace(",", "").strip()
        if not normalized:
            return None
        return float(normalized)
    return None