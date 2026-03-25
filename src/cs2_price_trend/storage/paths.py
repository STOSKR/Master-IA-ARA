"""Helpers for partitioned storage paths used by extraction pipelines."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from cs2_price_trend.quality.history_contract import normalize_source


def _normalize_run_id(run_id: str) -> str:
    normalized: str = run_id.strip().lower().replace(" ", "-")
    if not normalized:
        raise ValueError("run_id must not be blank")
    return normalized


@dataclass(frozen=True, slots=True)
class StorageRoots:
    """Base directories for raw, curated and dump datasets."""

    raw_root: Path
    curated_root: Path
    dumps_root: Path

    def expanded(self) -> StorageRoots:
        return StorageRoots(
            raw_root=self.raw_root.expanduser(),
            curated_root=self.curated_root.expanduser(),
            dumps_root=self.dumps_root.expanduser(),
        )


def ensure_directory(path: Path) -> Path:
    """Create directory recursively and return the same path."""

    path.mkdir(parents=True, exist_ok=True)
    return path


def partition_path(root: Path, partition_date: date, source: str) -> Path:
    """Build yyyy/mm/dd/source path partition under root."""

    source_partition: str = normalize_source(source)
    return (
        root
        / f"year={partition_date:%Y}"
        / f"month={partition_date:%m}"
        / f"day={partition_date:%d}"
        / f"source={source_partition}"
    )


def run_partition_path(root: Path, partition_date: date, source: str, run_id: str) -> Path:
    """Build yyyy/mm/dd/source/run_id path partition under root."""

    return partition_path(root, partition_date, source) / f"run_id={_normalize_run_id(run_id)}"


def _resolve_partition_dir(path: Path, *, create: bool) -> Path:
    return ensure_directory(path) if create else path


def raw_partition_dir(
    roots: StorageRoots, partition_date: date, source: str, create: bool = False
) -> Path:
    """Return partition directory for raw ingestion data."""

    directory: Path = partition_path(roots.expanded().raw_root, partition_date, source)
    return _resolve_partition_dir(directory, create=create)


def curated_partition_dir(
    roots: StorageRoots, partition_date: date, source: str, create: bool = False
) -> Path:
    """Return partition directory for curated output data."""

    directory: Path = partition_path(roots.expanded().curated_root, partition_date, source)
    return _resolve_partition_dir(directory, create=create)


def dumps_partition_dir(
    roots: StorageRoots, partition_date: date, source: str, create: bool = False
) -> Path:
    """Return partition directory for anomalous response body dumps."""

    directory: Path = partition_path(roots.expanded().dumps_root, partition_date, source)
    return _resolve_partition_dir(directory, create=create)


def raw_run_partition_dir(
    roots: StorageRoots,
    partition_date: date,
    source: str,
    run_id: str,
    create: bool = False,
) -> Path:
    """Return run-scoped partition directory for raw ingestion data."""

    directory: Path = run_partition_path(roots.expanded().raw_root, partition_date, source, run_id)
    return _resolve_partition_dir(directory, create=create)


def curated_run_partition_dir(
    roots: StorageRoots,
    partition_date: date,
    source: str,
    run_id: str,
    create: bool = False,
) -> Path:
    """Return run-scoped partition directory for curated output data."""

    directory: Path = run_partition_path(
        roots.expanded().curated_root, partition_date, source, run_id
    )
    return _resolve_partition_dir(directory, create=create)


def dumps_run_partition_dir(
    roots: StorageRoots,
    partition_date: date,
    source: str,
    run_id: str,
    create: bool = False,
) -> Path:
    """Return run-scoped partition directory for anomalous response body dumps."""

    directory: Path = run_partition_path(
        roots.expanded().dumps_root, partition_date, source, run_id
    )
    return _resolve_partition_dir(directory, create=create)
