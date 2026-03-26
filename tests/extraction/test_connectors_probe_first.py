from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from pytest import MonkeyPatch

from extraction.connectors.csfloat import CSFloatConnector
from extraction.errors import EndpointNotConfiguredError, UnknownResponseShapeError
from extraction.models import ExtractionTarget
from extraction.protocols import HttpResponse


@dataclass(slots=True)
class FakeHttpClient:
    responses: list[HttpResponse]
    calls: list[tuple[str, Mapping[str, str] | None, Mapping[str, str] | None]] = field(
        default_factory=list
    )

    async def get(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> HttpResponse:
        self.calls.append((url, params, headers))
        if not self.responses:
            raise RuntimeError("No fake response configured")
        return self.responses.pop(0)

    async def aclose(self) -> None:
        return None


def test_probe_first_requires_endpoint(monkeypatch: MonkeyPatch) -> None:
    async def scenario() -> None:
        monkeypatch.delenv("CSFLOAT_PROBE_ENDPOINT", raising=False)
        client = FakeHttpClient(responses=[])
        connector = CSFloatConnector(http_client=client, endpoint=None)
        target = ExtractionTarget(item_id="10", market_hash_name="M4A4 | Neo-Noir")

        try:
            await connector.extract(target)
        except EndpointNotConfiguredError:
            pass
        else:
            raise AssertionError("Expected EndpointNotConfiguredError")

        assert client.calls == []

    asyncio.run(scenario())


def test_csfloat_connector_happy_path() -> None:
    async def scenario() -> None:
        payload = {
            "data": [
                {
                    "timestamp": 1704067200,
                    "price": "12.34",
                    "volume": "7",
                    "currency": "usd",
                }
            ]
        }
        client = FakeHttpClient(
            responses=[
                HttpResponse(
                    url="https://api.csfloat.test/history",
                    status_code=200,
                    headers={"content-type": "application/json"},
                    body=json.dumps(payload).encode("utf-8"),
                )
            ]
        )
        connector = CSFloatConnector(
            http_client=client,
            endpoint="https://api.csfloat.test/history",
        )
        target = ExtractionTarget(item_id="11", market_hash_name="USP-S | Printstream")

        extraction = await connector.extract(target)

        assert extraction.source_name == "csfloat"
        assert len(extraction.points) == 1
        assert extraction.points[0].price == 12.34
        assert extraction.points[0].volume == 7
        assert extraction.points[0].currency == "USD"
        assert len(client.calls) == 1

    asyncio.run(scenario())


def test_csfloat_connector_unknown_shape_fails_explicitly() -> None:
    async def scenario() -> None:
        payload = {"unexpected": {"shape": True}}
        client = FakeHttpClient(
            responses=[
                HttpResponse(
                    url="https://api.csfloat.test/history",
                    status_code=200,
                    headers={"content-type": "application/json"},
                    body=json.dumps(payload).encode("utf-8"),
                )
            ]
        )
        connector = CSFloatConnector(
            http_client=client,
            endpoint="https://api.csfloat.test/history",
        )
        target = ExtractionTarget(item_id="12", market_hash_name="Glock-18 | Vogue")

        try:
            await connector.extract(target)
        except UnknownResponseShapeError:
            pass
        else:
            raise AssertionError("Expected UnknownResponseShapeError")

        assert len(client.calls) == 1

    asyncio.run(scenario())


def test_csfloat_connector_forwards_optional_auth_headers(
    monkeypatch: MonkeyPatch,
) -> None:
    async def scenario() -> None:
        payload = {
            "data": [
                {
                    "timestamp": 1704067200,
                    "price": "10.00",
                    "volume": "1",
                    "currency": "usd",
                }
            ]
        }
        client = FakeHttpClient(
            responses=[
                HttpResponse(
                    url="https://api.csfloat.test/history",
                    status_code=200,
                    headers={"content-type": "application/json"},
                    body=json.dumps(payload).encode("utf-8"),
                )
            ]
        )

        monkeypatch.setenv("CSFLOAT_API_KEY", "key-123")
        monkeypatch.setenv("CSFLOAT_COOKIE", "session=abc")
        monkeypatch.setenv("CSFLOAT_USER_AGENT", "test-agent")

        connector = CSFloatConnector(
            http_client=client,
            endpoint="https://api.csfloat.test/history",
        )
        target = ExtractionTarget(item_id="13", market_hash_name="AWP | Asiimov")

        await connector.extract(target)

        assert len(client.calls) == 1
        _, _, headers = client.calls[0]
        assert headers is not None
        assert headers["Authorization"] == "key-123"
        assert headers["Cookie"] == "session=abc"
        assert headers["User-Agent"] == "test-agent"

    asyncio.run(scenario())


def test_csfloat_connector_loads_cookie_header_from_auth_cookie_file(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    async def scenario() -> None:
        payload = {
            "data": [
                {
                    "timestamp": 1704067200,
                    "price": "10.00",
                    "volume": "1",
                    "currency": "usd",
                }
            ]
        }
        client = FakeHttpClient(
            responses=[
                HttpResponse(
                    url="https://api.csfloat.test/history",
                    status_code=200,
                    headers={"content-type": "application/json"},
                    body=json.dumps(payload).encode("utf-8"),
                )
            ]
        )

        cookie_store_path = tmp_path / "cookies.json"
        cookie_store_payload = {
            "platforms": {
                "csfloat": {
                    "cookies": [
                        {
                            "name": "session",
                            "value": "from-file",
                            "domain": "csfloat.com",
                            "path": "/",
                        }
                    ]
                }
            }
        }
        cookie_store_path.write_text(
            json.dumps(cookie_store_payload),
            encoding="utf-8",
        )

        monkeypatch.setenv("AUTH_COOKIES_PATH", str(cookie_store_path))
        monkeypatch.delenv("CSFLOAT_API_KEY", raising=False)
        monkeypatch.delenv("CSFLOAT_COOKIE", raising=False)
        monkeypatch.delenv("CSFLOAT_USER_AGENT", raising=False)

        connector = CSFloatConnector(
            http_client=client,
            endpoint="https://api.csfloat.test/history",
        )
        target = ExtractionTarget(item_id="14", market_hash_name="AK-47 | Neon Rider")

        await connector.extract(target)

        assert len(client.calls) == 1
        _, _, headers = client.calls[0]
        assert headers is not None
        assert headers["Cookie"] == "session=from-file"

    asyncio.run(scenario())
