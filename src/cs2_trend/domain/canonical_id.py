"""Deterministic canonical item identifier builder."""

from __future__ import annotations

import re

_SEPARATOR_PATTERN = re.compile(r"[\s_\-]+")


def normalize_identifier_component(value: str) -> str:
    """Normalize one identifier component to a deterministic slug token."""

    stripped = value.strip().lower()
    replaced = _SEPARATOR_PATTERN.sub("_", stripped)
    sanitized = "".join(char for char in replaced if char.isalnum() or char == "_")
    normalized = re.sub(r"_+", "_", sanitized).strip("_")
    if not normalized:
        raise ValueError("identifier component cannot be empty after normalization")
    return normalized


def build_canonical_item_id(
    *,
    weapon: str,
    skin_name: str,
    wear: str | None,
    is_stattrak: bool = False,
    is_souvenir: bool = False,
) -> str:
    """Build deterministic canonical id for one CS2 item."""

    components = [normalize_identifier_component(weapon), normalize_identifier_component(skin_name)]
    if wear:
        components.append(normalize_identifier_component(wear))
    if is_stattrak:
        components.append("stattrak")
    if is_souvenir:
        components.append("souvenir")
    return "__".join(components)