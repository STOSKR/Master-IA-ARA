from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from extraction.models import ExtractionTarget

_CONTEXT_CATEGORY_KEYS: tuple[str, ...] = (
    "object_type",
    "object_subtype",
    "type_name",
    "weapon_type",
    "weapon_family",
)


def resolve_catalog_path(*, catalog_dir: Path, catalog_path: Path | None) -> Path:
    """Resolve the catalog file path from explicit path or latest local JSON."""

    if catalog_path is not None:
        if not catalog_path.exists():
            raise FileNotFoundError(f"Catalog file does not exist: {catalog_path}")
        return catalog_path

    json_candidates = sorted(catalog_dir.glob("*.json"), reverse=True)
    if not json_candidates:
        raise FileNotFoundError(
            "No catalog JSON files found. Run `cs2trend phase0 catalog` before phase1 extraction."
        )
    return json_candidates[0]


def load_targets_from_catalog(
    *,
    catalog_path: Path,
    limit_items: int,
) -> tuple[ExtractionTarget, ...]:
    """Create extraction targets from catalog rows while preserving category context."""

    if limit_items < 1:
        raise ValueError("limit_items must be >= 1")

    rows = _read_catalog_rows(catalog_path)
    targets: list[ExtractionTarget] = []

    for row in rows:
        canonical_item_id = _as_str(row.get("canonical_item_id"))
        if canonical_item_id is None:
            continue

        source_keys = _coerce_json_object(row.get("source_keys"))
        metadata = _coerce_json_object(row.get("metadata"))

        market_hash_name = _resolve_market_hash_name(
            row=row,
            metadata=metadata,
            canonical_item_id=canonical_item_id,
        )
        item_id = (
            _as_str(source_keys.get("csfloat"))
            or _as_str(row.get("listing_id"))
            or canonical_item_id
        )

        context: dict[str, Any] = {
            "canonical_item_id": canonical_item_id,
            "currency": "USD",
        }
        for key in _CONTEXT_CATEGORY_KEYS:
            value = _as_str(row.get(key))
            if value is not None:
                context[key] = value

        targets.append(
            ExtractionTarget(
                item_id=item_id,
                market_hash_name=market_hash_name,
                context=context,
            )
        )

        if len(targets) >= limit_items:
            break

    if not targets:
        raise ValueError(
            f"No valid extraction targets found in catalog: {catalog_path}"
        )

    return tuple(targets)


def _read_catalog_rows(catalog_path: Path) -> tuple[dict[str, Any], ...]:
    if catalog_path.suffix.lower() == ".json":
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("Catalog JSON must contain a list of rows")
        return tuple(row for row in payload if isinstance(row, dict))

    if catalog_path.suffix.lower() == ".csv":
        frame = pd.read_csv(catalog_path)
        return tuple(dict(row) for _, row in frame.iterrows())

    raise ValueError(f"Unsupported catalog format: {catalog_path.suffix}")


def _resolve_market_hash_name(
    *,
    row: dict[str, Any],
    metadata: dict[str, Any],
    canonical_item_id: str,
) -> str:
    raw_market_name = _as_str(metadata.get("raw_market_name"))
    if raw_market_name is not None:
        return raw_market_name

    direct_name = _as_str(row.get("market_hash_name")) or _as_str(row.get("item_name"))
    if direct_name is not None:
        return direct_name

    weapon = _as_str(row.get("weapon"))
    skin_name = _as_str(row.get("skin_name"))
    if weapon is not None and skin_name is not None:
        return f"{weapon} | {skin_name}"

    return canonical_item_id


def _coerce_json_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw

    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed

    return {}


def _as_str(raw: Any) -> str | None:
    if isinstance(raw, str):
        value = raw.strip()
        return value or None
    if isinstance(raw, int):
        return str(raw)
    return None
