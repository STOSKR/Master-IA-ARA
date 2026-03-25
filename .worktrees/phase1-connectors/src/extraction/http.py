from __future__ import annotations

from collections.abc import Mapping

from extraction.protocols import AsyncHttpClient, HttpResponse

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover - optional dependency in minimal bootstrap
    httpx = None


class HttpxAsyncClient(AsyncHttpClient):
    """Adapter around httpx.AsyncClient that returns typed response envelopes."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 30.0,
        default_headers: Mapping[str, str] | None = None,
    ) -> None:
        if httpx is None:
            raise RuntimeError(
                "httpx is not installed. Install dependency before using HttpxAsyncClient."
            )
        self._client = httpx.AsyncClient(
            timeout=timeout_seconds,
            headers=dict(default_headers or {}),
        )

    async def get(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> HttpResponse:
        response = await self._client.get(url, params=params, headers=headers)
        return HttpResponse(
            url=str(response.url),
            status_code=response.status_code,
            headers=dict(response.headers),
            body=response.content,
        )

    async def aclose(self) -> None:
        await self._client.aclose()
