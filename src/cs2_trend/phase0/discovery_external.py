"""Discovery normalization for external reference datasets."""

from __future__ import annotations

from typing import Any, cast

from cs2_trend.phase0.discovery_helpers import (
    build_canonical_item_id_safe,
    infer_weapon_family,
    parse_market_name,
    safe_str,
)
from cs2_trend.phase0.models import JsonValue


def discover_catalog_records_from_external_dataset(
    *,
    object_type: str,
    payload: JsonValue,
    source_name: str = "csgo_api_reference",
) -> tuple[dict[str, Any], ...]:
    """Normalize one external category dataset into canonical discovery rows."""

    rows = _extract_external_rows(payload)
    records: list[dict[str, Any]] = []

    for row in rows:
        if object_type == "weapon":
            normalized = _normalize_external_weapon_record(
                row=row,
                source_name=source_name,
            )
        elif object_type in {"sticker", "container", "agent", "charm", "tool"}:
            normalized = _normalize_external_non_weapon_record(
                object_type=object_type,
                row=row,
                source_name=source_name,
            )
        else:
            normalized = _normalize_external_non_weapon_record(
                object_type="other",
                row=row,
                source_name=source_name,
            )

        if normalized is not None:
            records.append(normalized)

    return tuple(records)


def _extract_external_rows(payload: JsonValue) -> tuple[dict[str, Any], ...]:
    if isinstance(payload, list):
        return tuple(
            cast(dict[str, Any], row) for row in payload if isinstance(row, dict)
        )
    return ()


def _normalize_external_weapon_record(
    *,
    row: dict[str, Any],
    source_name: str,
) -> dict[str, Any] | None:
    market_hash_name = safe_str(row.get("market_hash_name")) or safe_str(
        row.get("name")
    )
    if market_hash_name is None:
        return None

    weapon_obj = row.get("weapon")
    pattern_obj = row.get("pattern")
    wear_obj = row.get("wear")

    weapon_name = (
        safe_str(weapon_obj.get("name")) if isinstance(weapon_obj, dict) else None
    )
    skin_name = (
        safe_str(pattern_obj.get("name")) if isinstance(pattern_obj, dict) else None
    )
    wear = safe_str(wear_obj.get("name")) if isinstance(wear_obj, dict) else None
    rarity = _extract_named_value(row.get("rarity"))
    collection = _extract_first_named_value(row.get("collections"))
    is_stattrak = bool(row.get("stattrak"))
    is_souvenir = bool(row.get("souvenir"))

    fallback_parsed = parse_market_name(market_hash_name)
    resolved_weapon = weapon_name or safe_str(fallback_parsed.get("weapon"))
    resolved_skin = skin_name or safe_str(fallback_parsed.get("skin_name"))
    resolved_wear = wear or safe_str(fallback_parsed.get("wear"))
    resolved_weapon_type = _extract_named_value(row.get("category")) or "Skin"
    resolved_item_name = safe_str(row.get("name")) or market_hash_name

    canonical_item_id = build_canonical_item_id_safe(
        object_type="weapon",
        item_name=resolved_item_name,
        weapon_name=resolved_weapon,
        skin_name=resolved_skin,
        wear=resolved_wear,
        is_stattrak=is_stattrak,
        is_souvenir=is_souvenir,
    )

    return {
        "canonical_item_id": canonical_item_id,
        "source": source_name,
        "object_type": "weapon",
        "object_subtype": resolved_weapon_type,
        "type_name": resolved_weapon_type,
        "market_hash_name": market_hash_name,
        "item_name": resolved_item_name,
        "weapon_type": resolved_weapon_type,
        "weapon_family": infer_weapon_family(resolved_weapon),
        "weapon_name": resolved_weapon,
        "skin_name": resolved_skin,
        "wear": resolved_wear,
        "rarity": rarity,
        "collection": collection,
        "is_stattrak": is_stattrak,
        "is_souvenir": is_souvenir,
        "listing_id": safe_str(row.get("id")),
        "asset_id": safe_str(row.get("paint_index")),
        "sample_price": None,
        "sample_currency": None,
        "raw_type": safe_str(row.get("type")),
    }


def _normalize_external_non_weapon_record(
    *,
    object_type: str,
    row: dict[str, Any],
    source_name: str,
) -> dict[str, Any] | None:
    market_hash_name = safe_str(row.get("market_hash_name")) or safe_str(
        row.get("name")
    )
    item_name = safe_str(row.get("name")) or market_hash_name
    if market_hash_name is None or item_name is None:
        return None

    rarity = _extract_named_value(row.get("rarity"))
    object_subtype = safe_str(row.get("type")) or object_type
    canonical_item_id = build_canonical_item_id_safe(
        object_type=object_type,
        item_name=item_name,
        weapon_name=None,
        skin_name=None,
        wear=None,
        is_stattrak=False,
        is_souvenir=False,
    )

    return {
        "canonical_item_id": canonical_item_id,
        "source": source_name,
        "object_type": object_type,
        "object_subtype": object_subtype,
        "type_name": object_subtype,
        "market_hash_name": market_hash_name,
        "item_name": item_name,
        "weapon_type": None,
        "weapon_family": None,
        "weapon_name": None,
        "skin_name": None,
        "wear": None,
        "rarity": rarity,
        "collection": _extract_first_named_value(row.get("collections")),
        "is_stattrak": False,
        "is_souvenir": False,
        "listing_id": safe_str(row.get("id")),
        "asset_id": safe_str(row.get("def_index")),
        "sample_price": None,
        "sample_currency": None,
        "raw_type": safe_str(row.get("type")),
    }


def _extract_named_value(value: Any) -> str | None:
    if isinstance(value, dict):
        return safe_str(value.get("name"))
    return safe_str(value)


def _extract_first_named_value(value: Any) -> str | None:
    if isinstance(value, list):
        for entry in value:
            if isinstance(entry, dict):
                candidate = safe_str(entry.get("name"))
                if candidate is not None:
                    return candidate
            elif isinstance(entry, str):
                candidate = safe_str(entry)
                if candidate is not None:
                    return candidate
    return None
