from __future__ import annotations

import json
from pathlib import Path

from pytest import MonkeyPatch

from extraction.auth_cookies import (
    build_cookie_header_for_platform,
    load_playwright_cookies_for_platform,
    resolve_platform_cookie_header,
)


def _write_cookie_fixture(path: Path) -> None:
    payload = {
        "schema_version": 1,
        "platforms": {
            "csfloat": {
                "cookies": [
                    {
                        "name": "session",
                        "value": "abc",
                        "domain": "csfloat.com",
                        "path": "/",
                        "secure": True,
                    },
                    {
                        "name": "region",
                        "value": "us",
                        "domain": ".csfloat.com",
                        "path": "/",
                    },
                ]
            },
            "steam": {
                "cookies": [
                    {
                        "name": "steamLoginSecure",
                        "value": "token",
                        "domain": "steamcommunity.com",
                        "path": "/",
                    }
                ]
            },
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_cookie_header_for_platform_reads_cookie_file(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    cookie_path = tmp_path / "cookies.json"
    _write_cookie_fixture(cookie_path)
    monkeypatch.setenv("AUTH_COOKIES_PATH", str(cookie_path))

    header = build_cookie_header_for_platform(platform="csfloat")

    assert header == "session=abc; region=us"


def test_resolve_platform_cookie_header_prefers_env_value(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    cookie_path = tmp_path / "cookies.json"
    _write_cookie_fixture(cookie_path)
    monkeypatch.setenv("AUTH_COOKIES_PATH", str(cookie_path))
    monkeypatch.setenv("CSFLOAT_COOKIE", "manual=override")

    resolved = resolve_platform_cookie_header(
        platform="csfloat",
        env_cookie_var="CSFLOAT_COOKIE",
    )

    assert resolved == "manual=override"


def test_load_playwright_cookies_for_platform_normalizes_shape(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    cookie_path = tmp_path / "cookies.json"
    _write_cookie_fixture(cookie_path)
    monkeypatch.setenv("AUTH_COOKIES_PATH", str(cookie_path))

    cookies = load_playwright_cookies_for_platform(platform="steam")

    assert len(cookies) == 1
    assert cookies[0]["name"] == "steamLoginSecure"
    assert cookies[0]["domain"] == "steamcommunity.com"
    assert cookies[0]["path"] == "/"
