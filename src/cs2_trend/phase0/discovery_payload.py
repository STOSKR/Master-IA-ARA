"""Discovery extraction from CSFloat paginated listings payloads."""

from __future__ import annotations

from typing import Any, cast

from cs2_trend.phase0.discovery_helpers import (
    build_canonical_item_id_safe,
    classify_object_type,
    extract_collection_name,
    first_str,
    infer_weapon_family,
    parse_market_name,
    to_float,
)
from cs2_trend.phase0.models import JsonValue


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

        market_hash_name = first_str(
            item,
            ("market_hash_name", "name", "item_name"),
        ) or first_str(
            listing,
            ("market_hash_name", "name", "item_name"),
        )
        item_name = first_str(item, ("item_name", "name")) or market_hash_name
        type_name = first_str(item, ("type_name", "type"))
        rarity = first_str(item, ("rarity_name", "rarity"))
        wear_name = first_str(item, ("wear_name",))
        collection = extract_collection_name(item)

        classification = classify_object_type(
            market_hash_name=market_hash_name,
            item_name=item_name,
            type_name=type_name,
        )
        object_type = classification["object_type"]
        object_subtype = classification["object_subtype"]

        parsed_name = parse_market_name(market_hash_name) if market_hash_name else None
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
            infer_weapon_family(weapon_name) if object_type == "weapon" else None
        )

        canonical_item_id = build_canonical_item_id_safe(
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
            "listing_id": first_str(listing, ("id", "listing_id")),
            "asset_id": first_str(item, ("asset_id", "item_id", "id")),
            "sample_price": to_float(listing.get("price")),
            "sample_currency": "USD",
            "raw_type": first_str(item, ("type",)),
        }
        records.append(record)

    return tuple(records)


def _extract_listings(payload: JsonValue) -> tuple[dict[str, Any], ...]:
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return tuple(
                cast(dict[str, Any], row) for row in data if isinstance(row, dict)
            )
    return ()
