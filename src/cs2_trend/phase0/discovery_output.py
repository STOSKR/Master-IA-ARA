"""Discovery artifact serialization and markdown rendering utilities."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


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
            group = weapon_types[weapon_type]
            weapon_count = (
                group.get("weapon_count", 0) if isinstance(group, dict) else 0
            )
            lines.append(f"- {weapon_type}: {weapon_count} weapons")

    lines.extend(["", "## Weapon Families", ""])
    weapon_families = summary.get("weapon_families", {})
    if isinstance(weapon_families, dict):
        for family_name in sorted(weapon_families):
            group = weapon_families[family_name]
            weapon_count = (
                group.get("weapon_count", 0) if isinstance(group, dict) else 0
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
