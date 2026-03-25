from __future__ import annotations

import pytest

from cs2_trend.domain.canonical_id import build_canonical_item_id, normalize_identifier_component


def test_build_canonical_item_id_is_deterministic() -> None:
    first = build_canonical_item_id(
        weapon="  AK-47  ",
        skin_name="Redline",
        wear="Field-Tested",
        is_stattrak=True,
        is_souvenir=False,
    )
    second = build_canonical_item_id(
        weapon="ak 47",
        skin_name=" redline ",
        wear="field tested",
        is_stattrak=True,
        is_souvenir=False,
    )

    assert first == "ak_47__redline__field_tested__stattrak"
    assert second == first


def test_normalize_identifier_component_rejects_empty_value() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        normalize_identifier_component("---")
