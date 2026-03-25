"""HTTP client implementations used by phase 0 probe services."""

from __future__ import annotations

import asyncio
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from cs2_trend.phase0.models import HttpJsonResponse, JsonValue


class UrllibJsonHttpClient:
    """Async wrapper around urllib for JSON endpoint probing."""

    def __init__(self, *, timeout_seconds: float, user_agent: str = "cs2-trend/0.1") -> None:
        self._timeout_seconds = timeout_seconds
        self._user_agent = user_agent

    async def fetch_json(self, *, endpoint: str) -> HttpJsonResponse:
        """Fetch endpoint and decode JSON payload in a worker thread."""

        return await asyncio.to_thread(self._fetch_json_sync, endpoint)

    def _fetch_json_sync(self, endpoint: str) -> HttpJsonResponse:
        request = Request(endpoint, headers={"User-Agent": self._user_agent})
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                status_code = int(response.status)
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            status_code = int(exc.code)
            body = exc.read().decode("utf-8", errors="replace")
        except URLError as exc:
            raise RuntimeError(f"network error while probing endpoint: {endpoint}") from exc

        try:
            payload: JsonValue = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ValueError(f"endpoint did not return valid JSON: {endpoint}") from exc

        return HttpJsonResponse(endpoint=endpoint, status_code=status_code, payload=payload)