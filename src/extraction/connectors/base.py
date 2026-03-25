from __future__ import annotations

from abc import ABC
from collections.abc import Callable, Iterable, Mapping

from extraction.cleaning import clean_price_points
from extraction.errors import (
    ConnectorHTTPError,
    EndpointNotConfiguredError,
    UnknownResponseShapeError,
)
from extraction.models import ConnectorExtraction, ExtractionTarget, PricePoint, ProbeSample
from extraction.protocols import AsyncHttpClient

PointParser = Callable[[ProbeSample, ExtractionTarget], Iterable[PricePoint]]


class ProbeFirstConnector(ABC):
    """Base connector enforcing probe-first behavior before parsing."""

    source_name: str

    def __init__(
        self,
        *,
        http_client: AsyncHttpClient,
        endpoint: str | None,
        parser: PointParser | None = None,
    ) -> None:
        self._http_client = http_client
        self._endpoint = endpoint
        self._parser = parser

    async def probe(self, target: ExtractionTarget) -> ProbeSample:
        if self._endpoint is None:
            raise EndpointNotConfiguredError(self.source_name)

        response = await self._http_client.get(
            self._endpoint,
            params=self.build_query_params(target),
            headers=self.build_headers(target),
        )
        sample = ProbeSample(
            source_name=self.source_name,
            url=response.url,
            status_code=response.status_code,
            headers=response.headers,
            body=response.body,
        )
        if response.status_code >= 400:
            raise ConnectorHTTPError(self.source_name, sample)
        return sample

    async def extract(self, target: ExtractionTarget) -> ConnectorExtraction:
        sample = await self.probe(target)
        parsed_points = self.parse_sample(sample=sample, target=target)
        cleaned_points = clean_price_points(parsed_points)
        return ConnectorExtraction(
            source_name=self.source_name,
            target=target,
            sample=sample,
            points=cleaned_points,
        )

    def parse_sample(
        self,
        *,
        sample: ProbeSample,
        target: ExtractionTarget,
    ) -> tuple[PricePoint, ...]:
        if self._parser is None:
            raise UnknownResponseShapeError(
                source_name=self.source_name,
                sample=sample,
                detail="parser not configured after probe stage",
            )

        parsed = tuple(self._parser(sample, target))
        if not parsed:
            raise UnknownResponseShapeError(
                source_name=self.source_name,
                sample=sample,
                detail="parser produced no price points",
            )
        return parsed

    def build_query_params(self, target: ExtractionTarget) -> Mapping[str, str]:
        return {"item_id": target.item_id, "market_hash_name": target.market_hash_name}

    def build_headers(self, _target: ExtractionTarget) -> Mapping[str, str]:
        return {}
