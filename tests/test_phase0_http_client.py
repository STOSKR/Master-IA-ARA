from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pytest import MonkeyPatch

from cs2_trend.phase0.http_clients import UrllibJsonHttpClient
from cs2_trend.phase0.models import HttpJsonResponse
from cs2_trend.phase0.services import CsfloatProbeService


@dataclass
class _FakeResponse:
    status: int
    _body: bytes
    headers: Mapping[str, str]

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> None:
        return None


def test_urllib_json_http_client_merges_headers(monkeypatch: MonkeyPatch) -> None:
    captured_headers: dict[str, str] = {}

    def fake_urlopen(request: Any, timeout: float) -> _FakeResponse:
        nonlocal captured_headers
        captured_headers = {
            key.lower(): value for key, value in dict(request.headers).items()
        }
        assert timeout == 5.0
        return _FakeResponse(status=200, _body=b'{"ok": true}', headers={})

    async def scenario() -> None:
        monkeypatch.setattr("cs2_trend.phase0.http_clients.urlopen", fake_urlopen)
        client = UrllibJsonHttpClient(
            timeout_seconds=5.0,
            default_headers={"X-Default": "one"},
        )
        response = await client.fetch_json(
            endpoint="https://example.test/api",
            headers={"X-Request": "two"},
        )

        assert response.status_code == 200
        assert response.payload == {"ok": True}

    asyncio.run(scenario())

    assert captured_headers["x-default"] == "one"
    assert captured_headers["x-request"] == "two"
    assert "user-agent" in captured_headers


def test_csfloat_probe_service_forwards_request_headers(tmp_path: Path) -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.headers: Mapping[str, str] | None = None

        async def fetch_json(
            self,
            *,
            endpoint: str,
            headers: Mapping[str, str] | None = None,
        ) -> HttpJsonResponse:
            self.headers = headers

            return HttpJsonResponse(
                endpoint=endpoint, status_code=200, payload={"data": []}
            )

    from cs2_trend.core.retry import RetryPolicy
    from cs2_trend.phase0.repositories import FileProbeDumpRepository

    async def scenario() -> None:
        client = FakeClient()
        service = CsfloatProbeService(
            http_client=client,
            dump_store=FileProbeDumpRepository(base_dir=tmp_path / "probes"),
            fallback_dump_dir=tmp_path / "dumps",
            retry_policy=RetryPolicy(max_attempts=1),
            request_headers={"Authorization": "test-key"},
        )
        await service.capture_sample(
            endpoint="https://csfloat.test/api", run_id="run-1"
        )

        assert client.headers == {"Authorization": "test-key"}

    asyncio.run(scenario())
