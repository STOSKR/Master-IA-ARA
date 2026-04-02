from __future__ import annotations

import os
from collections.abc import Mapping
from urllib.parse import quote

from extraction.cleaning import clean_price_points
from extraction.auth_cookies import resolve_platform_cookie_header
from extraction.connectors.base import ProbeFirstConnector
from extraction.connectors.json_parser import JsonShapeSpec, build_json_point_parser
from extraction.connectors.steam_line1 import parse_steam_line1_points
from extraction.connectors.steam_pricehistory import parse_steam_pricehistory_points
from extraction.errors import (
    ConnectorHTTPError,
    EndpointNotConfiguredError,
    UnknownResponseShapeError,
)
from extraction.models import ConnectorExtraction, ExtractionTarget, PricePoint, ProbeSample
from extraction.protocols import AsyncHttpClient

_DEFAULT_STEAM_PRICEHISTORY_ENDPOINT = "https://steamcommunity.com/market/pricehistory/"
_DEFAULT_STEAM_LISTING_ENDPOINT = (
    "https://steamcommunity.com/market/listings/730/{market_hash_name}"
)


class SteamConnector(ProbeFirstConnector):
    """Probe-first connector for Steam Community Market."""

    source_name = "steam"

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
        )

        def parse_with_fallback(
            sample: ProbeSample,
            target: ExtractionTarget,
        ) -> tuple[PricePoint, ...]:
            probe_sample = sample
            try:
                return json_parser(probe_sample, target)
            except UnknownResponseShapeError:
                pass

            try:
                return parse_steam_pricehistory_points(sample=probe_sample, target=target)
            except ValueError:
                pass

            try:
                return parse_steam_line1_points(sample=probe_sample, target=target)
            except ValueError as exc:
                raise UnknownResponseShapeError(
                    source_name=self.source_name,
                    sample=probe_sample,
                    detail=f"unsupported steam payload ({exc})",
                ) from exc

        super().__init__(
            http_client=http_client,
            endpoint=(
                endpoint
                or os.getenv("STEAM_PROBE_ENDPOINT")
                or _DEFAULT_STEAM_PRICEHISTORY_ENDPOINT
            ),
            parser=parse_with_fallback,
        )

    async def probe(self, target: ExtractionTarget) -> ProbeSample:
        endpoint = self._resolve_endpoint(target)
        sample = await self._probe_endpoint(endpoint=endpoint, target=target)
        if sample.status_code < 400:
            return sample

        if self._is_pricehistory_endpoint(endpoint):
            fallback_sample = await self._probe_listing_endpoint(target=target)
            if fallback_sample.status_code < 400:
                return fallback_sample

        raise ConnectorHTTPError(self.source_name, sample)

    async def extract(self, target: ExtractionTarget) -> ConnectorExtraction:
        sample = await self.probe(target)

        try:
            parsed_points = self.parse_sample(sample=sample, target=target)
        except UnknownResponseShapeError:
            if not self._is_pricehistory_endpoint(sample.url):
                raise
            sample = await self._probe_listing_endpoint(target=target)
            if sample.status_code >= 400:
                raise ConnectorHTTPError(self.source_name, sample)
            parsed_points = self.parse_sample(sample=sample, target=target)

        cleaned_points = clean_price_points(parsed_points)
        return ConnectorExtraction(
            source_name=self.source_name,
            target=target,
            sample=sample,
            points=cleaned_points,
        )

    def build_query_params(self, target: ExtractionTarget) -> Mapping[str, str]:
        if self._endpoint is None:
            raise EndpointNotConfiguredError(self.source_name)
        return self._build_query_params_for_endpoint(endpoint=self._endpoint, target=target)

    def build_headers(self, _target: ExtractionTarget) -> Mapping[str, str]:
        headers: dict[str, str] = {}
        cookie = resolve_platform_cookie_header(
            platform=self.source_name,
            env_cookie_var="STEAM_COOKIE",
        )
        user_agent = os.getenv("STEAM_USER_AGENT")
        if cookie:
            headers["Cookie"] = cookie
        if user_agent:
            headers["User-Agent"] = user_agent
        return headers

    def _resolve_endpoint(self, target: ExtractionTarget) -> str:
        if self._endpoint is None:
            raise EndpointNotConfiguredError(self.source_name)

        if "{market_hash_name}" in self._endpoint:
            encoded_name = quote(target.market_hash_name, safe="")
            return self._endpoint.format(market_hash_name=encoded_name)

        return self._endpoint

    async def _probe_listing_endpoint(self, *, target: ExtractionTarget) -> ProbeSample:
        listing_endpoint = self._resolve_listing_endpoint(target)
        return await self._probe_endpoint(endpoint=listing_endpoint, target=target)

    async def _probe_endpoint(
        self,
        *,
        endpoint: str,
        target: ExtractionTarget,
    ) -> ProbeSample:
        response = await self._http_client.get(
            endpoint,
            params=self._build_query_params_for_endpoint(endpoint=endpoint, target=target),
            headers=self.build_headers(target),
        )
        return ProbeSample(
            source_name=self.source_name,
            url=response.url,
            status_code=response.status_code,
            headers=response.headers,
            body=response.body,
        )

    def _build_query_params_for_endpoint(
        self,
        *,
        endpoint: str,
        target: ExtractionTarget,
    ) -> Mapping[str, str]:
        if "{market_hash_name}" in endpoint:
            return {}

        if self._is_pricehistory_endpoint(endpoint):
            return {
                "appid": "730",
                "market_hash_name": target.market_hash_name,
            }

        return {
            "market_hash_name": target.market_hash_name,
            "item_id": target.item_id,
        }

    def _resolve_listing_endpoint(self, target: ExtractionTarget) -> str:
        encoded_name = quote(target.market_hash_name, safe="")
        return _DEFAULT_STEAM_LISTING_ENDPOINT.format(market_hash_name=encoded_name)

    def _is_pricehistory_endpoint(self, endpoint: str) -> bool:
        return "pricehistory" in endpoint.lower()
