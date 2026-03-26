"""Phase 0 probing, catalog, and discovery services."""

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
from cs2_trend.phase0.http_clients import UrllibJsonHttpClient
from cs2_trend.phase0.repositories import FileCatalogRepository, FileProbeDumpRepository
from cs2_trend.phase0.services import (
    CatalogService,
    CsfloatCatalogParser,
    CsfloatProbeService,
)

__all__ = [
    "CatalogService",
    "CsfloatCatalogParser",
    "CsfloatProbeService",
    "FileCatalogRepository",
    "FileProbeDumpRepository",
    "UrllibJsonHttpClient",
    "build_discovery_summary",
    "build_missing_fields_report",
    "discover_catalog_records_from_external_dataset",
    "discover_catalog_records_from_payload",
    "find_low_volume_categories",
    "has_missing_fields",
    "merge_catalog_records",
    "write_discovery_outputs",
]
