from __future__ import annotations

from pathlib import Path

from cs2_trend.phase0.discovery import (
    build_discovery_summary,
    build_missing_fields_report,
    discover_catalog_records_from_external_dataset,
    discover_catalog_records_from_payload,
    find_low_volume_categories,
    has_missing_fields,
    merge_catalog_records,
    write_discovery_outputs,
)
from cs2_trend.phase0.models import JsonValue


def test_discovery_extracts_multiple_object_types() -> None:
    payload: JsonValue = {
        "data": [
            {
                "id": "l1",
                "price": 100.0,
                "item": {
                    "market_hash_name": "AK-47 | Case Hardened (Factory New)",
                    "item_name": "AK-47 | Case Hardened",
                    "type_name": "Rifle",
                    "wear_name": "Factory New",
                    "rarity_name": "Classified",
                    "asset_id": "a1",
                },
            },
            {
                "id": "l2",
                "price": 12.0,
                "item": {
                    "market_hash_name": "Sticker | Dragon (Foil)",
                    "item_name": "Sticker | Dragon",
                    "type_name": "Sticker",
                    "rarity_name": "Remarkable",
                },
            },
            {
                "id": "l3",
                "price": 4.5,
                "item": {
                    "market_hash_name": "Operation Bravo Case",
                    "item_name": "Operation Bravo Case",
                    "type_name": "Container",
                },
            },
        ]
    }

    records = discover_catalog_records_from_payload(payload)
    merged = merge_catalog_records(records)
    summary = build_discovery_summary(merged)

    assert len(merged) == 3
    assert summary["object_types"]["weapon"]["count"] == 1
    assert summary["object_types"]["sticker"]["count"] == 1
    assert summary["object_types"]["container"]["count"] == 1
    assert "Rifle" in summary["weapon_types"]
    assert "AK-47" in summary["weapon_types"]["Rifle"]["weapons"]


def test_discovery_outputs_and_missing_fields_report(tmp_path: Path) -> None:
    payload: JsonValue = {
        "data": [
            {
                "id": "l1",
                "price": 100.0,
                "item": {
                    "market_hash_name": "AK-47 | Asiimov (Field-Tested)",
                    "item_name": "AK-47 | Asiimov",
                    "type_name": "Rifle",
                },
            }
        ]
    }

    records = merge_catalog_records(discover_catalog_records_from_payload(payload))
    summary = build_discovery_summary(records)
    missing = build_missing_fields_report(records)

    paths = write_discovery_outputs(
        base_dir=tmp_path,
        output_name="catalog_discovery_test",
        records=records,
        summary=summary,
        missing_fields=missing,
    )

    assert paths["records_json"].exists()
    assert paths["records_csv"].exists()
    assert paths["summary_json"].exists()
    assert paths["summary_md"].exists()
    assert paths["missing_json"].exists()
    assert paths["missing_md"].exists()

    weapon_missing = missing.get("weapon")
    assert isinstance(weapon_missing, dict)
    assert "rarity" in weapon_missing


def test_find_low_volume_categories_uses_thresholds() -> None:
    summary = {
        "object_types": {
            "weapon": {"count": 420, "objects": []},
            "sticker": {"count": 58, "objects": []},
            "container": {"count": 5, "objects": []},
        }
    }
    minimums = {
        "weapon": 1000,
        "sticker": 500,
        "container": 10,
        "agent": 20,
    }

    low = find_low_volume_categories(summary, minimums)

    assert low == ("agent", "container", "sticker", "weapon")


def test_discovery_external_dataset_normalizes_weapon_records() -> None:
    payload: JsonValue = [
        {
            "id": "skin-1",
            "name": "AK-47 | Redline (Field-Tested)",
            "market_hash_name": "AK-47 | Redline (Field-Tested)",
            "weapon": {"name": "AK-47"},
            "pattern": {"name": "Redline"},
            "wear": {"name": "Field-Tested"},
            "rarity": {"name": "Classified"},
            "stattrak": False,
            "souvenir": False,
            "paint_index": "282",
        }
    ]

    rows = discover_catalog_records_from_external_dataset(
        object_type="weapon",
        payload=payload,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["object_type"] == "weapon"
    assert row["weapon_name"] == "AK-47"
    assert row["skin_name"] == "Redline"
    assert row["wear"] == "Field-Tested"
    assert row["source"] == "csgo_api_reference"


def test_discovery_external_dataset_normalizes_sticker_records() -> None:
    payload: JsonValue = [
        {
            "id": "sticker-1",
            "name": "Sticker | Test Event",
            "market_hash_name": None,
            "rarity": {"name": "Remarkable"},
            "type": "Event",
            "def_index": "1234",
        }
    ]

    rows = discover_catalog_records_from_external_dataset(
        object_type="sticker",
        payload=payload,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["object_type"] == "sticker"
    assert row["item_name"] == "Sticker | Test Event"
    assert row["market_hash_name"] == "Sticker | Test Event"


def test_has_missing_fields_detects_empty_report() -> None:
    report = {
        "weapon": {
            "rarity": {
                "missing_count": 0,
                "total": 10,
                "missing_ratio": 0.0,
                "examples": [],
            }
        }
    }

    assert not has_missing_fields(report)
