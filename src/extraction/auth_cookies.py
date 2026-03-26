from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def resolve_auth_cookie_file_path(cookie_file: Path | None = None) -> Path:
    """Resolve cookie file path from explicit path, env var, or default."""

    if cookie_file is not None:
        return cookie_file.expanduser()

    configured = os.getenv("AUTH_COOKIES_PATH")
    if configured is not None and configured.strip():
        return Path(configured.strip()).expanduser()

    return Path("cookies.json")


def load_platform_cookie_records(
    *,
    platform: str,
    cookie_file: Path | None = None,
) -> tuple[dict[str, Any], ...]:
    """Read and return cookie records for one platform from local cookie file."""

    payload = _read_cookie_payload(resolve_auth_cookie_file_path(cookie_file))
    if payload is None:
        return ()

    section = _extract_platform_section(payload=payload, platform=platform)
    return _coerce_cookie_list(section)


def build_cookie_header_for_platform(
    *,
    platform: str,
    cookie_file: Path | None = None,
) -> str | None:
    """Build HTTP Cookie header value from locally captured cookie records."""

    records = load_platform_cookie_records(platform=platform, cookie_file=cookie_file)
    pairs = _cookie_name_value_pairs(records)
    if not pairs:
        return None

    return "; ".join(f"{name}={value}" for name, value in pairs)


def resolve_platform_cookie_header(
    *,
    platform: str,
    env_cookie_var: str,
    cookie_file: Path | None = None,
) -> str | None:
    """Resolve cookie header using env var first, then local cookie file fallback."""

    explicit = os.getenv(env_cookie_var)
    if explicit is not None and explicit.strip():
        return explicit.strip()

    return build_cookie_header_for_platform(platform=platform, cookie_file=cookie_file)


def load_playwright_cookies_for_platform(
    *,
    platform: str,
    cookie_file: Path | None = None,
) -> tuple[dict[str, Any], ...]:
    """Return cookie records normalized for Playwright context.addCookies usage."""

    normalized: list[dict[str, Any]] = []
    for record in load_platform_cookie_records(
        platform=platform, cookie_file=cookie_file
    ):
        name = record.get("name")
        value = record.get("value")
        domain = record.get("domain")
        if (
            not isinstance(name, str)
            or not isinstance(value, str)
            or not isinstance(domain, str)
        ):
            continue
        if not name.strip() or not domain.strip():
            continue

        entry: dict[str, Any] = {
            "name": name,
            "value": value,
            "domain": domain,
            "path": record.get("path") if isinstance(record.get("path"), str) else "/",
        }

        secure = record.get("secure")
        if isinstance(secure, bool):
            entry["secure"] = secure

        http_only = record.get("httpOnly")
        if isinstance(http_only, bool):
            entry["httpOnly"] = http_only

        expires = record.get("expires")
        if isinstance(expires, (int, float)):
            entry["expires"] = int(expires)

        same_site = record.get("sameSite")
        if isinstance(same_site, str) and same_site:
            entry["sameSite"] = same_site

        normalized.append(entry)

    return tuple(normalized)


def _read_cookie_payload(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None

    try:
        raw_payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    if isinstance(raw_payload, dict):
        return raw_payload
    return None


def _extract_platform_section(*, payload: dict[str, Any], platform: str) -> Any:
    platforms = payload.get("platforms")
    if isinstance(platforms, dict) and platform in platforms:
        return platforms[platform]

    return payload.get(platform)


def _coerce_cookie_list(section: Any) -> tuple[dict[str, Any], ...]:
    if isinstance(section, dict):
        cookie_items = section.get("cookies")
        if isinstance(cookie_items, list):
            return tuple(item for item in cookie_items if isinstance(item, dict))

    if isinstance(section, list):
        return tuple(item for item in section if isinstance(item, dict))

    return ()


def _cookie_name_value_pairs(
    records: tuple[dict[str, Any], ...],
) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []

    for record in records:
        name = record.get("name")
        value = record.get("value")
        if not isinstance(name, str) or not isinstance(value, str):
            continue
        normalized_name = name.strip()
        if not normalized_name:
            continue
        pairs.append((normalized_name, value))

    return tuple(pairs)
