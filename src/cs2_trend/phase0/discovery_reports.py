"""Discovery merge, summary, and missing-fields analytics utilities."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from cs2_trend.phase0.discovery_helpers import is_missing, safe_str

_REQUIRED_FIELDS_BY_TYPE: dict[str, tuple[str, ...]] = {
    "weapon": (
        "weapon_type",
        "weapon_family",
        "weapon_name",
        "skin_name",
        "rarity",
        "market_hash_name",
    ),
    "sticker": ("item_name", "rarity", "sample_price", "market_hash_name"),
    "container": ("item_name", "sample_price", "market_hash_name"),
    "agent": ("item_name", "rarity", "sample_price", "market_hash_name"),
    "charm": ("item_name", "sample_price", "market_hash_name"),
    "tool": ("item_name", "sample_price", "market_hash_name"),
    "other": ("item_name", "sample_price", "market_hash_name"),
}


def merge_catalog_records(
    records: tuple[dict[str, Any], ...],
) -> tuple[dict[str, Any], ...]:
    """Merge duplicate canonical records preferring non-empty values."""

    by_id: dict[str, dict[str, Any]] = {}
    for record in records:
        canonical_item_id = safe_str(record.get("canonical_item_id"))
        if canonical_item_id is None:
            continue

        existing = by_id.get(canonical_item_id)
        if existing is None:
            by_id[canonical_item_id] = dict(record)
            continue

        for key, value in record.items():
            if is_missing(existing.get(key)) and not is_missing(value):
                existing[key] = value

    return tuple(sorted(by_id.values(), key=lambda row: str(row["canonical_item_id"])))


def build_discovery_summary(records: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    """Build grouped counts and taxonomy from normalized catalog records."""

    type_to_items: dict[str, set[str]] = defaultdict(set)
    weapon_tree: dict[str, dict[str, dict[str, set[str]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(set))
    )
    weapon_family_tree: dict[str, dict[str, dict[str, set[str]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(set))
    )

    for record in records:
        object_type = safe_str(record.get("object_type")) or "other"
        item_name = safe_str(record.get("item_name"))
        if item_name is not None:
            type_to_items[object_type].add(item_name)

        if object_type == "weapon":
            weapon_type = safe_str(record.get("weapon_type")) or "unknown"
            weapon_family = safe_str(record.get("weapon_family")) or "unknown"
            weapon_name = safe_str(record.get("weapon_name")) or "unknown"
            skin_name = safe_str(record.get("skin_name")) or "unknown"
            wear = safe_str(record.get("wear")) or "no_wear"
            weapon_tree[weapon_type][weapon_name][skin_name].add(wear)
            weapon_family_tree[weapon_family][weapon_name][skin_name].add(wear)

    object_types: dict[str, Any] = {}
    for object_type in sorted(type_to_items):
        items = sorted(type_to_items[object_type])
        object_types[object_type] = {
            "count": len(items),
            "objects": items,
        }

    weapon_types = _build_weapon_taxonomy(weapon_tree)
    weapon_families = _build_weapon_taxonomy(weapon_family_tree)

    return {
        "total_unique_items": len(records),
        "object_type_count": len(object_types),
        "object_types": object_types,
        "weapon_types": weapon_types,
        "weapon_families": weapon_families,
    }


def build_missing_fields_report(records: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    """Build a report of fields that could not be populated from extracted data."""

    report: dict[str, Any] = {}

    for object_type, required_fields in _REQUIRED_FIELDS_BY_TYPE.items():
        matching = [row for row in records if row.get("object_type") == object_type]
        if not matching:
            continue

        field_report: dict[str, Any] = {}
        for field_name in required_fields:
            missing_rows = [row for row in matching if is_missing(row.get(field_name))]
            examples = [
                safe_str(row.get("canonical_item_id"))
                for row in missing_rows[:5]
                if safe_str(row.get("canonical_item_id")) is not None
            ]
            field_report[field_name] = {
                "missing_count": len(missing_rows),
                "total": len(matching),
                "missing_ratio": round(len(missing_rows) / len(matching), 4),
                "examples": examples,
            }

        report[object_type] = field_report

    return report


def has_missing_fields(missing_fields: dict[str, Any]) -> bool:
    """Return True when at least one required field has missing rows."""

    for object_payload in missing_fields.values():
        if not isinstance(object_payload, dict):
            continue
        for field_payload in object_payload.values():
            if not isinstance(field_payload, dict):
                continue
            missing_count = field_payload.get("missing_count")
            if isinstance(missing_count, int) and missing_count > 0:
                return True
    return False


def find_low_volume_categories(
    summary: dict[str, Any],
    minimum_counts: dict[str, int],
) -> tuple[str, ...]:
    """Return categories whose discovered object count is below threshold."""

    object_types = summary.get("object_types")
    if not isinstance(object_types, dict):
        return tuple(sorted(minimum_counts))

    low_categories: list[str] = []
    for object_type, minimum_count in sorted(minimum_counts.items()):
        payload = object_types.get(object_type)
        current_count = 0
        if isinstance(payload, dict):
            count_value = payload.get("count")
            if isinstance(count_value, int):
                current_count = count_value
        if current_count < minimum_count:
            low_categories.append(object_type)

    return tuple(low_categories)


def _build_weapon_taxonomy(
    tree: dict[str, dict[str, dict[str, set[str]]]],
) -> dict[str, Any]:
    payload: dict[str, Any] = {}

    for group_name in sorted(tree):
        weapons_payload: dict[str, Any] = {}
        for weapon_name in sorted(tree[group_name]):
            skins_payload: dict[str, Any] = {}
            for skin_name in sorted(tree[group_name][weapon_name]):
                wears = sorted(tree[group_name][weapon_name][skin_name])
                skins_payload[skin_name] = {
                    "wear_count": len(wears),
                    "wears": wears,
                }

            weapons_payload[weapon_name] = {
                "skin_count": len(skins_payload),
                "skins": skins_payload,
            }

        payload[group_name] = {
            "weapon_count": len(weapons_payload),
            "weapons": weapons_payload,
        }

    return payload
