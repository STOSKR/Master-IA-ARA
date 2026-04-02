from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from pytest import MonkeyPatch

from extraction.connectors.buff163 import Buff163Connector
from extraction.connectors.csmoney import CSMoneyConnector
from extraction.connectors.csfloat import CSFloatConnector
from extraction.connectors.steam import SteamConnector
from extraction.errors import EndpointNotConfiguredError
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


def test_csfloat_connector_unknown_shape_uses_simulated_fallback() -> None:
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

        extraction = await connector.extract(target)

        assert extraction.source_name == "csfloat"
        assert len(extraction.points) == 16
        assert extraction.sample.headers.get("x-simulated") == "true"
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


def test_csfloat_connector_parses_created_at_listings_shape() -> None:
    async def scenario() -> None:
        payload = {
            "data": [
                {
                    "created_at": "2026-03-26T10:47:08.000Z",
                    "price": 123.45,
                }
            ]
        }
        client = FakeHttpClient(
            responses=[
                HttpResponse(
                    url="https://api.csfloat.test/listings",
                    status_code=200,
                    headers={"content-type": "application/json"},
                    body=json.dumps(payload).encode("utf-8"),
                )
            ]
        )

        connector = CSFloatConnector(
            http_client=client,
            endpoint="https://api.csfloat.test/listings",
        )
        target = ExtractionTarget(item_id="15", market_hash_name="AK-47 | Vulcan")

        extraction = await connector.extract(target)

        assert len(extraction.points) == 1
        assert extraction.points[0].price == 123.45

    asyncio.run(scenario())


def test_steam_connector_parses_inline_line1_fallback() -> None:
    async def scenario() -> None:
        html_payload = """
        <html><body>
        <script>
        var line1=[["Mar 25 2026 00: +0",10.5,"3"],["Mar 25 2026 01: +0",11.0,"4"]];
        </script>
        </body></html>
        """
        client = FakeHttpClient(
            responses=[
                HttpResponse(
                    url="https://steamcommunity.com/market/listings/730/item",
                    status_code=200,
                    headers={"content-type": "text/html"},
                    body=html_payload.encode("utf-8"),
                )
            ]
        )
        connector = SteamConnector(
            http_client=client,
            endpoint="https://steamcommunity.com/market/listings/730/item",
        )
        target = ExtractionTarget(item_id="21", market_hash_name="AK-47 | Redline")

        extraction = await connector.extract(target)

        assert extraction.source_name == "steam"
        assert len(extraction.points) == 2
        assert extraction.points[0].price == 10.5
        assert extraction.points[0].volume == 3

    asyncio.run(scenario())


def test_steam_connector_default_endpoint_uses_pricehistory() -> None:
    async def scenario() -> None:
        payload = {
            "success": True,
            "prices": [["Mar 25 2026 00: +0", "$10.50", "3"]],
        }
        client = FakeHttpClient(
            responses=[
                HttpResponse(
                    url=(
                        "https://steamcommunity.com/market/pricehistory/"
                        "?appid=730&market_hash_name=AK-47%20%7C%20Redline%20%28Field-Tested%29"
                    ),
                    status_code=200,
                    headers={"content-type": "application/json"},
                    body=json.dumps(payload).encode("utf-8"),
                )
            ]
        )
        connector = SteamConnector(http_client=client)
        target = ExtractionTarget(item_id="21", market_hash_name="AK-47 | Redline (Field-Tested)")

        extraction = await connector.extract(target)

        assert extraction.source_name == "steam"
        assert len(extraction.points) == 1
        assert len(client.calls) == 1
        url, params, _ = client.calls[0]
        assert url == "https://steamcommunity.com/market/pricehistory/"
        assert params is not None
        assert params["appid"] == "730"
        assert params["market_hash_name"] == "AK-47 | Redline (Field-Tested)"

    asyncio.run(scenario())


def test_steam_connector_falls_back_to_listing_when_pricehistory_payload_is_blocked() -> None:
    async def scenario() -> None:
        fallback_html = """
        <html><body>
        <script>
        var line1=[["Mar 25 2026 00: +0",10.5,"3"],["Mar 25 2026 01: +0",10.7,"4"]];
        </script>
        </body></html>
        """
        client = FakeHttpClient(
            responses=[
                HttpResponse(
                    url=(
                        "https://steamcommunity.com/market/pricehistory/"
                        "?appid=730&market_hash_name=AK-47%20%7C%20Redline"
                    ),
                    status_code=200,
                    headers={"content-type": "application/json"},
                    body=json.dumps({"success": False}).encode("utf-8"),
                ),
                HttpResponse(
                    url="https://steamcommunity.com/market/listings/730/AK-47%20%7C%20Redline",
                    status_code=200,
                    headers={"content-type": "text/html"},
                    body=fallback_html.encode("utf-8"),
                ),
            ]
        )
        connector = SteamConnector(http_client=client)
        target = ExtractionTarget(item_id="22", market_hash_name="AK-47 | Redline")

        extraction = await connector.extract(target)

        assert extraction.source_name == "steam"
        assert len(extraction.points) == 2
        assert len(client.calls) == 2
        first_url, first_params, _ = client.calls[0]
        second_url, second_params, _ = client.calls[1]
        assert first_url == "https://steamcommunity.com/market/pricehistory/"
        assert first_params is not None
        assert first_params["appid"] == "730"
        assert "market/listings/730/AK-47%20%7C%20Redline" in second_url
        assert second_params == {}

    asyncio.run(scenario())


def test_steam_connector_loads_cookie_header_from_auth_cookie_file(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    async def scenario() -> None:
        payload = {
            "success": True,
            "prices": [["Mar 25 2026 00: +0", "$10.50", "3"]],
        }
        client = FakeHttpClient(
            responses=[
                HttpResponse(
                    url="https://steamcommunity.com/market/pricehistory/?appid=730",
                    status_code=200,
                    headers={"content-type": "application/json"},
                    body=json.dumps(payload).encode("utf-8"),
                )
            ]
        )

        cookie_store_path = tmp_path / "cookies.json"
        cookie_store_payload = {
            "platforms": {
                "steam": {
                    "cookies": [
                        {
                            "name": "steamLoginSecure",
                            "value": "from-file",
                            "domain": "steamcommunity.com",
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
        monkeypatch.delenv("STEAM_COOKIE", raising=False)
        monkeypatch.delenv("STEAM_USER_AGENT", raising=False)

        connector = SteamConnector(http_client=client)
        target = ExtractionTarget(item_id="23", market_hash_name="AK-47 | Vulcan")

        await connector.extract(target)

        assert len(client.calls) == 1
        _, _, headers = client.calls[0]
        assert headers is not None
        assert headers["Cookie"] == "steamLoginSecure=from-file"

    asyncio.run(scenario())


def test_buff163_connector_parses_public_sell_order_shape() -> None:
    async def scenario() -> None:
        payload = {
            "code": "OK",
            "data": {
                "items": [
                    {
                        "created_at": 1704067200,
                        "price": "6",
                    }
                ]
            },
        }
        client = FakeHttpClient(
            responses=[
                HttpResponse(
                    url="https://buff.163.com/api/market/goods/sell_order",
                    status_code=200,
                    headers={"content-type": "application/json"},
                    body=json.dumps(payload).encode("utf-8"),
                )
            ]
        )
        connector = Buff163Connector(http_client=client)
        target = ExtractionTarget(item_id="886670", market_hash_name="PP-Bizon | Space Cat (Minimal Wear)")

        extraction = await connector.extract(target)

        assert extraction.source_name == "buff163"
        assert len(extraction.points) == 1
        assert extraction.points[0].price == 6.0
        assert extraction.points[0].currency == "CNY"
        _, params, _ = client.calls[0]
        assert params is not None
        assert params["goods_id"] == "886670"
        assert params["game"] == "csgo"

    asyncio.run(scenario())


def test_buff163_connector_uses_simulated_fallback_on_unknown_shape() -> None:
    async def scenario() -> None:
        payload = {"code": "OK", "data": {"items": []}}
        client = FakeHttpClient(
            responses=[
                HttpResponse(
                    url="https://buff.163.com/api/market/goods/sell_order",
                    status_code=200,
                    headers={"content-type": "application/json"},
                    body=json.dumps(payload).encode("utf-8"),
                )
            ]
        )
        connector = Buff163Connector(http_client=client)
        target = ExtractionTarget(item_id="unknown", market_hash_name="Unknown Item")

        extraction = await connector.extract(target)

        assert extraction.source_name == "buff163"
        assert len(extraction.points) == 12
        assert extraction.sample.headers.get("x-simulated") == "true"

    asyncio.run(scenario())


def test_csmoney_connector_uses_simulated_fallback_when_blocked() -> None:
    async def scenario() -> None:
        client = FakeHttpClient(
            responses=[
                HttpResponse(
                    url="https://cs.money/",
                    status_code=200,
                    headers={"content-type": "text/html"},
                    body=b"<html><body>challenge</body></html>",
                )
            ]
        )
        connector = CSMoneyConnector(http_client=client)
        target = ExtractionTarget(item_id="42", market_hash_name="AK-47 | Redline (Field-Tested)")

        extraction = await connector.extract(target)

        assert extraction.source_name == "csmoney"
        assert len(extraction.points) == 24
        assert extraction.sample.headers.get("x-simulated") == "true"

    asyncio.run(scenario())
