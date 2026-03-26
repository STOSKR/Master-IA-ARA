"""Catalog discovery utilities for CSFloat paginated listings."""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, cast

from cs2_trend.domain.canonical_id import build_canonical_item_id
from cs2_trend.phase0.models import JsonValue

_STAT_TRACK_PREFIX = re.compile(r"^StatTrak(?:™)?\s+", re.IGNORECASE)
_SOUVENIR_PREFIX = re.compile(r"^Souvenir\s+", re.IGNORECASE)
_WEAR_SUFFIX = re.compile(r"\(([^()]+)\)\s*$")
_COLLECTION_PATTERN = re.compile(r"([A-Za-z0-9 '\-]+ Collection)", re.IGNORECASE)
_CONTAINER_PATTERN = re.compile(
    r"\b(case|capsule|container|package|crate)\b",
    re.IGNORECASE,
)

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


def discover_catalog_records_from_payload(
    payload: JsonValue,
) -> tuple[dict[str, Any], ...]:
    """Extract normalized catalog possibility records from one listings payload."""

    listings = _extract_listings(payload)
    records: list[dict[str, Any]] = []

    for listing in listings:
        item_value = listing.get("item")
        item: dict[str, Any]
        if isinstance(item_value, dict):
            item = cast(dict[str, Any], item_value)
        else:
            item = {}

        market_hash_name = _first_str(
            item,
            ("market_hash_name", "name", "item_name"),
        ) or _first_str(
            listing,
            ("market_hash_name", "name", "item_name"),
        )
        item_name = _first_str(item, ("item_name", "name")) or market_hash_name
        type_name = _first_str(item, ("type_name", "type"))
        rarity = _first_str(item, ("rarity_name", "rarity"))
        wear_name = _first_str(item, ("wear_name",))
        collection = _extract_collection_name(item)

        classification = _classify_object_type(
            market_hash_name=market_hash_name,
            item_name=item_name,
            type_name=type_name,
        )
        object_type = classification["object_type"]
        object_subtype = classification["object_subtype"]

        parsed_name = _parse_market_name(market_hash_name) if market_hash_name else None
        weapon_name: str | None = None
        skin_name: str | None = None
        resolved_wear = wear_name

        is_stattrak = bool(item.get("is_stattrak"))
        is_souvenir = bool(item.get("is_souvenir"))

        if parsed_name is not None:
            if object_type == "weapon":
                weapon_name = parsed_name["weapon"]
                skin_name = parsed_name["skin_name"]
            resolved_wear = parsed_name["wear"] or wear_name
            is_stattrak = is_stattrak or parsed_name["is_stattrak"]
            is_souvenir = is_souvenir or parsed_name["is_souvenir"]

        weapon_family = (
            _infer_weapon_family(weapon_name) if object_type == "weapon" else None
        )

        canonical_item_id = _build_canonical_item_id_safe(
            object_type=object_type,
            item_name=item_name,
            weapon_name=weapon_name,
            skin_name=skin_name,
            wear=resolved_wear,
            is_stattrak=is_stattrak,
            is_souvenir=is_souvenir,
        )

        record = {
            "canonical_item_id": canonical_item_id,
            "source": "csfloat",
            "object_type": object_type,
            "object_subtype": object_subtype,
            "type_name": type_name,
            "market_hash_name": market_hash_name,
            "item_name": item_name,
            "weapon_type": type_name if object_type == "weapon" else None,
            "weapon_family": weapon_family,
            "weapon_name": weapon_name,
            "skin_name": skin_name,
            "wear": resolved_wear,
            "rarity": rarity,
            "collection": collection,
            "is_stattrak": is_stattrak,
            "is_souvenir": is_souvenir,
            "listing_id": _first_str(listing, ("id", "listing_id")),
            "asset_id": _first_str(item, ("asset_id", "item_id", "id")),
            "sample_price": _to_float(listing.get("price")),
            "sample_currency": "USD",
            "raw_type": _first_str(item, ("type",)),
        }
        records.append(record)

    return tuple(records)


def merge_catalog_records(
    records: tuple[dict[str, Any], ...],
) -> tuple[dict[str, Any], ...]:
    """Merge duplicate canonical records preferring non-empty values."""

    by_id: dict[str, dict[str, Any]] = {}
    for record in records:
        canonical_item_id = _safe_str(record.get("canonical_item_id"))
        if canonical_item_id is None:
            continue

        existing = by_id.get(canonical_item_id)
        if existing is None:
            by_id[canonical_item_id] = dict(record)
            continue

        for key, value in record.items():
            if _is_missing(existing.get(key)) and not _is_missing(value):
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
        object_type = _safe_str(record.get("object_type")) or "other"
        item_name = _safe_str(record.get("item_name"))
        if item_name is not None:
            type_to_items[object_type].add(item_name)

        if object_type == "weapon":
            weapon_type = _safe_str(record.get("weapon_type")) or "unknown"
            weapon_family = _safe_str(record.get("weapon_family")) or "unknown"
            weapon_name = _safe_str(record.get("weapon_name")) or "unknown"
            skin_name = _safe_str(record.get("skin_name")) or "unknown"
            wear = _safe_str(record.get("wear")) or "no_wear"
            weapon_tree[weapon_type][weapon_name][skin_name].add(wear)
            weapon_family_tree[weapon_family][weapon_name][skin_name].add(wear)

    object_types: dict[str, Any] = {}
    for object_type in sorted(type_to_items):
        items = sorted(type_to_items[object_type])
        object_types[object_type] = {
            "count": len(items),
            "objects": items,
        }

    weapon_types: dict[str, Any] = {}
    for weapon_type in sorted(weapon_tree):
        weapons_payload: dict[str, Any] = {}
        for weapon_name in sorted(weapon_tree[weapon_type]):
            skins_payload: dict[str, Any] = {}
            for skin_name in sorted(weapon_tree[weapon_type][weapon_name]):
                wears = sorted(weapon_tree[weapon_type][weapon_name][skin_name])
                skins_payload[skin_name] = {
                    "wear_count": len(wears),
                    "wears": wears,
                }

            weapons_payload[weapon_name] = {
                "skin_count": len(skins_payload),
                "skins": skins_payload,
            }

        weapon_types[weapon_type] = {
            "weapon_count": len(weapons_payload),
            "weapons": weapons_payload,
        }

    weapon_families: dict[str, Any] = {}
    for family_name in sorted(weapon_family_tree):
        weapons_payload = {}
        for weapon_name in sorted(weapon_family_tree[family_name]):
            skins_payload = {}
            for skin_name in sorted(weapon_family_tree[family_name][weapon_name]):
                wears = sorted(weapon_family_tree[family_name][weapon_name][skin_name])
                skins_payload[skin_name] = {
                    "wear_count": len(wears),
                    "wears": wears,
                }

            weapons_payload[weapon_name] = {
                "skin_count": len(skins_payload),
                "skins": skins_payload,
            }

        weapon_families[family_name] = {
            "weapon_count": len(weapons_payload),
            "weapons": weapons_payload,
        }

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
            missing_rows = [row for row in matching if _is_missing(row.get(field_name))]
            examples = [
                _safe_str(row.get("canonical_item_id"))
                for row in missing_rows[:5]
                if _safe_str(row.get("canonical_item_id")) is not None
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
            normalized = _normalize_external_weapon_record(row=row, source_name=source_name)
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


def write_discovery_outputs(
    *,
    base_dir: Path,
    output_name: str,
    records: tuple[dict[str, Any], ...],
    summary: dict[str, Any],
    missing_fields: dict[str, Any],
    include_missing_report: bool = True,
) -> dict[str, Path]:
    """Persist discovery artifacts as CSV/JSON/Markdown reports."""

    base_dir.mkdir(parents=True, exist_ok=True)

    records_json_path = base_dir / f"{output_name}.json"
    records_csv_path = base_dir / f"{output_name}.csv"
    summary_json_path = base_dir / f"{output_name}_summary.json"
    summary_md_path = base_dir / f"{output_name}_summary.md"
    missing_json_path = base_dir / f"{output_name}_missing_fields.json"
    missing_md_path = base_dir / f"{output_name}_missing_fields.md"

    records_json_path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    headers = (
        "canonical_item_id",
        "source",
        "object_type",
        "object_subtype",
        "type_name",
        "market_hash_name",
        "item_name",
        "weapon_type",
        "weapon_family",
        "weapon_name",
        "skin_name",
        "wear",
        "rarity",
        "collection",
        "is_stattrak",
        "is_souvenir",
        "listing_id",
        "asset_id",
        "sample_price",
        "sample_currency",
        "raw_type",
    )
    with records_csv_path.open("w", newline="", encoding="utf-8") as csv_handle:
        writer = csv.DictWriter(csv_handle, fieldnames=list(headers))
        writer.writeheader()
        for row in records:
            writer.writerow({header: row.get(header) for header in headers})

    summary_json_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    summary_md_path.write_text(_summary_to_markdown(summary), encoding="utf-8")

    outputs: dict[str, Path] = {
        "records_json": records_json_path,
        "records_csv": records_csv_path,
        "summary_json": summary_json_path,
        "summary_md": summary_md_path,
    }

    if include_missing_report:
        missing_json_path.write_text(
            json.dumps(missing_fields, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        missing_md_path.write_text(
            _missing_fields_to_markdown(missing_fields),
            encoding="utf-8",
        )
        outputs["missing_json"] = missing_json_path
        outputs["missing_md"] = missing_md_path

    return outputs


def _extract_listings(payload: JsonValue) -> tuple[dict[str, Any], ...]:
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return tuple(
                cast(dict[str, Any], row) for row in data if isinstance(row, dict)
            )
    return ()


def _extract_external_rows(payload: JsonValue) -> tuple[dict[str, Any], ...]:
    if isinstance(payload, list):
        return tuple(cast(dict[str, Any], row) for row in payload if isinstance(row, dict))
    return ()


def _normalize_external_weapon_record(
    *,
    row: dict[str, Any],
    source_name: str,
) -> dict[str, Any] | None:
    market_hash_name = _safe_str(row.get("market_hash_name")) or _safe_str(row.get("name"))
    if market_hash_name is None:
        return None

    weapon_obj = row.get("weapon")
    pattern_obj = row.get("pattern")
    wear_obj = row.get("wear")

    weapon_name = _safe_str(weapon_obj.get("name")) if isinstance(weapon_obj, dict) else None
    skin_name = _safe_str(pattern_obj.get("name")) if isinstance(pattern_obj, dict) else None
    wear = _safe_str(wear_obj.get("name")) if isinstance(wear_obj, dict) else None
    rarity = _extract_named_value(row.get("rarity"))
    collection = _extract_first_named_value(row.get("collections"))
    is_stattrak = bool(row.get("stattrak"))
    is_souvenir = bool(row.get("souvenir"))

    fallback_parsed = _parse_market_name(market_hash_name)
    resolved_weapon = weapon_name or _safe_str(fallback_parsed.get("weapon"))
    resolved_skin = skin_name or _safe_str(fallback_parsed.get("skin_name"))
    resolved_wear = wear or _safe_str(fallback_parsed.get("wear"))
    resolved_weapon_type = _extract_named_value(row.get("category")) or "Skin"
    resolved_item_name = _safe_str(row.get("name")) or market_hash_name

    canonical_item_id = _build_canonical_item_id_safe(
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
        "weapon_family": _infer_weapon_family(resolved_weapon),
        "weapon_name": resolved_weapon,
        "skin_name": resolved_skin,
        "wear": resolved_wear,
        "rarity": rarity,
        "collection": collection,
        "is_stattrak": is_stattrak,
        "is_souvenir": is_souvenir,
        "listing_id": _safe_str(row.get("id")),
        "asset_id": _safe_str(row.get("paint_index")),
        "sample_price": None,
        "sample_currency": None,
        "raw_type": _safe_str(row.get("type")),
    }


def _normalize_external_non_weapon_record(
    *,
    object_type: str,
    row: dict[str, Any],
    source_name: str,
) -> dict[str, Any] | None:
    market_hash_name = _safe_str(row.get("market_hash_name")) or _safe_str(row.get("name"))
    item_name = _safe_str(row.get("name")) or market_hash_name
    if market_hash_name is None or item_name is None:
        return None

    rarity = _extract_named_value(row.get("rarity"))
    object_subtype = _safe_str(row.get("type")) or object_type
    canonical_item_id = _build_canonical_item_id_safe(
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
        "listing_id": _safe_str(row.get("id")),
        "asset_id": _safe_str(row.get("def_index")),
        "sample_price": None,
        "sample_currency": None,
        "raw_type": _safe_str(row.get("type")),
    }


def _extract_named_value(value: Any) -> str | None:
    if isinstance(value, dict):
        return _safe_str(value.get("name"))
    return _safe_str(value)


def _extract_first_named_value(value: Any) -> str | None:
    if isinstance(value, list):
        for entry in value:
            if isinstance(entry, dict):
                candidate = _safe_str(entry.get("name"))
                if candidate is not None:
                    return candidate
            elif isinstance(entry, str):
                candidate = _safe_str(entry)
                if candidate is not None:
                    return candidate
    return None


def _first_str(obj: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = obj.get(key)
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned:
                return cleaned
        if isinstance(value, int):
            return str(value)
    return None


def _safe_str(value: Any) -> str | None:
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned else None
    if isinstance(value, int):
        return str(value)
    return None


def _to_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _extract_collection_name(item: dict[str, Any]) -> str | None:
    for key in ("collection", "collection_name", "set_name", "set"):
        value = _safe_str(item.get(key))
        if value is not None:
            return value

    description = _safe_str(item.get("description"))
    if description is None:
        return None

    match = _COLLECTION_PATTERN.search(description)
    if match is None:
        return None
    return match.group(1).strip()


def _classify_object_type(
    *,
    market_hash_name: str | None,
    item_name: str | None,
    type_name: str | None,
) -> dict[str, str]:
    type_name_lc = (type_name or "").lower()
    text = " ".join(
        part for part in (market_hash_name, item_name, type_name) if part
    ).lower()

    if "sticker" in text:
        return {"object_type": "sticker", "object_subtype": type_name or "sticker"}
    if "graffiti" in text:
        return {"object_type": "graffiti", "object_subtype": type_name or "graffiti"}
    if "music kit" in text:
        return {"object_type": "music_kit", "object_subtype": type_name or "music_kit"}

    if type_name_lc in {"agent"} or ("agent" in text and "sticker" not in text):
        return {"object_type": "agent", "object_subtype": type_name or "agent"}
    if type_name_lc in {"charm"} or "charm" in text:
        return {"object_type": "charm", "object_subtype": type_name or "charm"}
    weapon_markers = (
        "rifle",
        "pistol",
        "smg",
        "sniper",
        "shotgun",
        "machinegun",
        "knife",
        "gloves",
        "bayonet",
        "karambit",
    )
    if any(marker in text for marker in weapon_markers) or (
        market_hash_name is not None and "|" in market_hash_name
    ):
        return {"object_type": "weapon", "object_subtype": type_name or "weapon"}

    if type_name_lc in {"container", "case", "capsule"}:
        return {"object_type": "container", "object_subtype": type_name or "container"}

    market_name_lc = (market_hash_name or "").lower()
    if "|" not in market_name_lc and _CONTAINER_PATTERN.search(market_name_lc):
        return {"object_type": "container", "object_subtype": type_name or "container"}
    if "key" in text:
        return {"object_type": "tool", "object_subtype": type_name or "key"}

    return {"object_type": "other", "object_subtype": type_name or "other"}


def _parse_market_name(market_name: str) -> dict[str, Any]:
    candidate = market_name.strip()
    is_stattrak = False
    is_souvenir = False

    stattrak_match = _STAT_TRACK_PREFIX.match(candidate)
    if stattrak_match is not None:
        is_stattrak = True
        candidate = candidate[stattrak_match.end() :].strip()

    souvenir_match = _SOUVENIR_PREFIX.match(candidate)
    if souvenir_match is not None:
        is_souvenir = True
        candidate = candidate[souvenir_match.end() :].strip()

    wear: str | None = None
    wear_match = _WEAR_SUFFIX.search(candidate)
    if wear_match is not None:
        wear = wear_match.group(1).strip()
        candidate = candidate[: wear_match.start()].strip()

    if "|" in candidate:
        weapon_part, skin_part = candidate.split("|", maxsplit=1)
        weapon = weapon_part.strip()
        skin_name = skin_part.strip()
    else:
        weapon = candidate
        skin_name = candidate

    return {
        "weapon": weapon,
        "skin_name": skin_name,
        "wear": wear,
        "is_stattrak": is_stattrak,
        "is_souvenir": is_souvenir,
    }


def _build_canonical_item_id_safe(
    *,
    object_type: str,
    item_name: str | None,
    weapon_name: str | None,
    skin_name: str | None,
    wear: str | None,
    is_stattrak: bool,
    is_souvenir: bool,
) -> str:
    if object_type == "weapon":
        resolved_weapon = weapon_name or item_name or "unknown_weapon"
        resolved_skin = skin_name or item_name or "unknown_skin"
        return build_canonical_item_id(
            weapon=resolved_weapon,
            skin_name=resolved_skin,
            wear=wear,
            is_stattrak=is_stattrak,
            is_souvenir=is_souvenir,
        )

    resolved_name = item_name or "unknown_item"
    return build_canonical_item_id(
        weapon=object_type,
        skin_name=resolved_name,
        wear=None,
        is_stattrak=False,
        is_souvenir=False,
    )


def _infer_weapon_family(weapon_name: str | None) -> str:
    if weapon_name is None:
        return "unknown"

    candidate = weapon_name.lower()
    if candidate.startswith("★") or "knife" in candidate or "bayonet" in candidate:
        return "knife"
    if any(marker in candidate for marker in ("gloves", "hand wraps", "bloodhound")):
        return "gloves"
    if candidate in {
        "ak-47",
        "m4a4",
        "m4a1-s",
        "famas",
        "galil ar",
        "sg 553",
        "aug",
    }:
        return "rifle"
    if candidate in {"awp", "ssg 08", "scar-20", "g3sg1"}:
        return "sniper_rifle"
    if candidate in {"mac-10", "mp9", "mp7", "mp5-sd", "ump-45", "p90", "pp-bizon"}:
        return "smg"
    if candidate in {
        "glock-18",
        "usp-s",
        "p2000",
        "p250",
        "desert eagle",
        "dual berettas",
        "five-seven",
        "cz75-auto",
        "r8 revolver",
        "tec-9",
    }:
        return "pistol"
    if candidate in {"nova", "xm1014", "mag-7", "sawed-off"}:
        return "shotgun"
    if candidate in {"m249", "negev"}:
        return "machinegun"
    return "other_weapon"


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def _summary_to_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Catalog Discovery Summary",
        "",
        f"- Total unique items: {summary.get('total_unique_items', 0)}",
        f"- Object types discovered: {summary.get('object_type_count', 0)}",
        "",
        "## Objects By Type",
        "",
    ]

    object_types = summary.get("object_types", {})
    if isinstance(object_types, dict):
        for object_type in sorted(object_types):
            entry = object_types[object_type]
            count = entry.get("count", 0) if isinstance(entry, dict) else 0
            lines.append(f"- {object_type}: {count}")

    lines.extend(["", "## Weapon Taxonomy", ""])
    weapon_types = summary.get("weapon_types", {})
    if isinstance(weapon_types, dict):
        for weapon_type in sorted(weapon_types):
            payload = weapon_types[weapon_type]
            weapon_count = (
                payload.get("weapon_count", 0) if isinstance(payload, dict) else 0
            )
            lines.append(f"- {weapon_type}: {weapon_count} weapons")

    lines.extend(["", "## Weapon Families", ""])
    weapon_families = summary.get("weapon_families", {})
    if isinstance(weapon_families, dict):
        for family_name in sorted(weapon_families):
            payload = weapon_families[family_name]
            weapon_count = (
                payload.get("weapon_count", 0) if isinstance(payload, dict) else 0
            )
            lines.append(f"- {family_name}: {weapon_count} weapons")

    lines.append("")
    return "\n".join(lines)


def _missing_fields_to_markdown(missing_fields: dict[str, Any]) -> str:
    lines = [
        "# Missing Fields Report",
        "",
        "Fields below could not be fully populated from extracted source payloads.",
        "",
    ]

    for object_type in sorted(missing_fields):
        lines.append(f"## {object_type}")
        lines.append("")
        payload = missing_fields[object_type]
        if not isinstance(payload, dict):
            continue

        for field_name in sorted(payload):
            field_payload = payload[field_name]
            if not isinstance(field_payload, dict):
                continue
            lines.append(
                f"- {field_name}: missing {field_payload.get('missing_count', 0)}"
                f"/{field_payload.get('total', 0)}"
                f" ({field_payload.get('missing_ratio', 0)})"
            )

        lines.append("")

    return "\n".join(lines)
