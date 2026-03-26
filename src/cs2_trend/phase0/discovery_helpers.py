"""Shared helpers for catalog discovery parsing and normalization."""

from __future__ import annotations

import re
from typing import Any

from cs2_trend.domain.canonical_id import build_canonical_item_id

_STAT_TRACK_PREFIX = re.compile(r"^StatTrak(?:™)?\s+", re.IGNORECASE)
_SOUVENIR_PREFIX = re.compile(r"^Souvenir\s+", re.IGNORECASE)
_WEAR_SUFFIX = re.compile(r"\(([^()]+)\)\s*$")
_COLLECTION_PATTERN = re.compile(r"([A-Za-z0-9 '\-]+ Collection)", re.IGNORECASE)
_CONTAINER_PATTERN = re.compile(
    r"\b(case|capsule|container|package|crate)\b",
    re.IGNORECASE,
)


def first_str(obj: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    """Return first present non-empty string/int field from keys list."""

    for key in keys:
        value = obj.get(key)
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned:
                return cleaned
        if isinstance(value, int):
            return str(value)
    return None


def safe_str(value: Any) -> str | None:
    """Normalize strings and ints to compact string values."""

    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned else None
    if isinstance(value, int):
        return str(value)
    return None


def to_float(value: Any) -> float | None:
    """Convert scalar-like value to float when possible."""

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


def extract_collection_name(item: dict[str, Any]) -> str | None:
    """Resolve collection name from explicit fields or description text."""

    for key in ("collection", "collection_name", "set_name", "set"):
        value = safe_str(item.get(key))
        if value is not None:
            return value

    description = safe_str(item.get("description"))
    if description is None:
        return None

    match = _COLLECTION_PATTERN.search(description)
    if match is None:
        return None
    return match.group(1).strip()


def classify_object_type(
    *,
    market_hash_name: str | None,
    item_name: str | None,
    type_name: str | None,
) -> dict[str, str]:
    """Infer canonical object type/subtype from market and metadata text."""

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


def parse_market_name(market_name: str) -> dict[str, Any]:
    """Parse market name into weapon/skin/wear and flags."""

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


def build_canonical_item_id_safe(
    *,
    object_type: str,
    item_name: str | None,
    weapon_name: str | None,
    skin_name: str | None,
    wear: str | None,
    is_stattrak: bool,
    is_souvenir: bool,
) -> str:
    """Build canonical id for weapon and non-weapon object types."""

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


def infer_weapon_family(weapon_name: str | None) -> str:
    """Map weapon name to broad weapon family."""

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


def is_missing(value: Any) -> bool:
    """Return True when value should be considered empty/missing."""

    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False
