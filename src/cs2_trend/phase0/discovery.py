"""Catalog discovery public API for phase0 services.

This module re-exports discovery functions while implementation lives in
smaller focused modules.
"""

from __future__ import annotations

from cs2_trend.phase0.discovery_external import (
    discover_catalog_records_from_external_dataset,
)
from cs2_trend.phase0.discovery_output import write_discovery_outputs
from cs2_trend.phase0.discovery_payload import discover_catalog_records_from_payload
from cs2_trend.phase0.discovery_reports import (
    build_discovery_summary,
    build_missing_fields_report,
    find_low_volume_categories,
    has_missing_fields,
    merge_catalog_records,
)

__all__ = [
    "build_discovery_summary",
    "build_missing_fields_report",
    "discover_catalog_records_from_external_dataset",
    "discover_catalog_records_from_payload",
    "find_low_volume_categories",
    "has_missing_fields",
    "merge_catalog_records",
    "write_discovery_outputs",
]
