from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from cs2_price_trend.storage.paths import (
    StorageRoots,
    curated_partition_dir,
    curated_run_partition_dir,
    dumps_partition_dir,
    dumps_run_partition_dir,
    raw_partition_dir,
    raw_run_partition_dir,
)


def test_partition_helpers_build_expected_path_structure() -> None:
    roots = StorageRoots(
        raw_root=Path("~/raw"), curated_root=Path("~/curated"), dumps_root=Path("~/dumps")
    )
    target_date = date(2026, 3, 25)

    raw_path = raw_partition_dir(roots, target_date, "Steam")
    curated_path = curated_partition_dir(roots, target_date, "Steam")
    dumps_path = dumps_partition_dir(roots, target_date, "Steam")

    assert "year=2026" in str(raw_path)
    assert "month=03" in str(curated_path)
    assert "day=25" in str(dumps_path)
    assert str(raw_path).endswith("source=steam")


def test_run_partition_helpers_build_expected_path_structure() -> None:
    roots = StorageRoots(
        raw_root=Path("~/raw"), curated_root=Path("~/curated"), dumps_root=Path("~/dumps")
    )
    target_date = date(2026, 3, 25)

    raw_path = raw_run_partition_dir(roots, target_date, "Steam", run_id=" Run 001 ")
    curated_path = curated_run_partition_dir(roots, target_date, "Steam", run_id=" Run 001 ")
    dumps_path = dumps_run_partition_dir(roots, target_date, "Steam", run_id=" Run 001 ")

    assert str(raw_path).endswith("source=steam/run_id=run-001")
    assert str(curated_path).endswith("source=steam/run_id=run-001")
    assert str(dumps_path).endswith("source=steam/run_id=run-001")


def test_run_partition_helpers_create_directories(tmp_path: Path) -> None:
    roots = StorageRoots(
        raw_root=tmp_path / "raw",
        curated_root=tmp_path / "curated",
        dumps_root=tmp_path / "dumps",
    )
    target_date = date(2026, 3, 25)

    raw_path = raw_run_partition_dir(roots, target_date, "steam", run_id="run-a", create=True)
    curated_path = curated_run_partition_dir(
        roots, target_date, "steam", run_id="run-a", create=True
    )
    dumps_path = dumps_run_partition_dir(roots, target_date, "steam", run_id="run-a", create=True)

    assert raw_path.exists()
    assert raw_path.is_dir()
    assert curated_path.exists()
    assert curated_path.is_dir()
    assert dumps_path.exists()
    assert dumps_path.is_dir()


def test_run_partition_helpers_reject_blank_run_id() -> None:
    roots = StorageRoots(
        raw_root=Path("~/raw"), curated_root=Path("~/curated"), dumps_root=Path("~/dumps")
    )

    with pytest.raises(ValueError, match="run_id must not be blank"):
        raw_run_partition_dir(roots, date(2026, 3, 25), "steam", run_id="   ")


def test_partition_helpers_reject_unknown_source() -> None:
    roots = StorageRoots(
        raw_root=Path("~/raw"), curated_root=Path("~/curated"), dumps_root=Path("~/dumps")
    )

    with pytest.raises(ValueError, match="Unknown source"):
        raw_partition_dir(roots, date(2026, 3, 25), "market-x")
