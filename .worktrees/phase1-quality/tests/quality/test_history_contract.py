from __future__ import annotations

import pytest

from cs2_price_trend.quality.history_contract import normalize_source


def test_normalize_source_lowercases_and_trims() -> None:
    assert normalize_source(" SteamDT ") == "steamdt"


def test_normalize_source_rejects_blank_value() -> None:
    with pytest.raises(ValueError, match="source must not be blank"):
        normalize_source("  ")


def test_normalize_source_rejects_unknown_source() -> None:
    with pytest.raises(ValueError, match="Unknown source"):
        normalize_source("unknown_market")
