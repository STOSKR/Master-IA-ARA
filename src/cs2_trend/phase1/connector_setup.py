from __future__ import annotations

import os
from collections.abc import Sequence

from cs2_price_trend.quality import normalize_source
from cs2_trend.core.config import AppConfig
from extraction.auth_cookies import build_cookie_header_for_platform
from extraction.connectors import (
    Buff163Connector,
    CSFloatConnector,
    CSMoneyConnector,
    SteamConnector,
    SteamdtConnector,
)
from extraction.protocols import AsyncHttpClient, MarketConnector

_SOURCE_TO_ENV: dict[str, str] = {
    "steam": "STEAM_PROBE_ENDPOINT",
    "steamdt": "STEAMDT_PROBE_ENDPOINT",
    "buff163": "BUFF163_PROBE_ENDPOINT",
    "csmoney": "CSMONEY_PROBE_ENDPOINT",
    "csfloat": "CSFLOAT_PROBE_ENDPOINT",
}

_CSFLOAT_AUTH_ENV_NAMES: tuple[str, ...] = ("CSFLOAT_API_KEY", "CSFLOAT_COOKIE")


def normalize_sources(selected_sources: Sequence[str]) -> tuple[str, ...]:
    """Normalize and deduplicate selected source names."""

    if not selected_sources:
        selected_sources = ("steam", "steamdt", "buff163")

    normalized = tuple(normalize_source(source) for source in selected_sources)
    return tuple(dict.fromkeys(normalized))


def build_default_connectors(
    *,
    config: AppConfig,
    selected_sources: Sequence[str],
    http_client: AsyncHttpClient,
) -> Sequence[MarketConnector]:
    """Build connector instances for selected sources."""

    connector_builders: dict[str, MarketConnector] = {
        "steam": SteamConnector(
            http_client=http_client,
            endpoint=config.steam_probe_endpoint,
        ),
        "steamdt": SteamdtConnector(
            http_client=http_client,
            endpoint=config.steamdt_probe_endpoint,
        ),
        "buff163": Buff163Connector(
            http_client=http_client,
            endpoint=config.buff163_probe_endpoint,
        ),
        "csmoney": CSMoneyConnector(
            http_client=http_client,
            endpoint=config.csmoney_probe_endpoint,
        ),
        "csfloat": CSFloatConnector(
            http_client=http_client,
            endpoint=config.csfloat_history_endpoint or config.csfloat_probe_endpoint,
        ),
    }

    connectors = [
        connector_builders[source]
        for source in selected_sources
        if source in connector_builders
    ]
    return tuple(connectors)


def ensure_sources_are_configured(
    *, config: AppConfig, selected_sources: Sequence[str]
) -> None:
    """Validate endpoint and auth prerequisites for all selected sources."""

    missing: list[str] = []

    for source in selected_sources:
        endpoint = _endpoint_for_source(config=config, source=source)
        env_name = _SOURCE_TO_ENV[source]
        env_value = os.getenv(env_name)

        if endpoint is None and (env_value is None or not env_value.strip()):
            missing.append(f"{source} ({env_name})")

        if source == "csfloat" and not _has_csfloat_auth():
            missing.append("csfloat authentication (CSFLOAT_API_KEY or CSFLOAT_COOKIE)")

    if missing:
        joined = ", ".join(sorted(missing))
        raise ValueError(
            "Missing endpoint configuration for selected sources: "
            f"{joined}. Set environment variables or AppConfig endpoint fields."
        )


def _has_csfloat_auth() -> bool:
    for env_name in _CSFLOAT_AUTH_ENV_NAMES:
        value = os.getenv(env_name)
        if value and value.strip():
            return True

    cookie_header = build_cookie_header_for_platform(platform="csfloat")
    if cookie_header and cookie_header.strip():
        return True

    return False


def _endpoint_for_source(*, config: AppConfig, source: str) -> str | None:
    if source == "steam":
        return _normalized_optional(config.steam_probe_endpoint)
    if source == "steamdt":
        return _normalized_optional(config.steamdt_probe_endpoint)
    if source == "buff163":
        return _normalized_optional(config.buff163_probe_endpoint)
    if source == "csmoney":
        return _normalized_optional(config.csmoney_probe_endpoint)
    if source == "csfloat":
        return _normalized_optional(
            config.csfloat_history_endpoint or config.csfloat_probe_endpoint
        )
    raise ValueError(f"Unsupported source: {source}")


def _normalized_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None
