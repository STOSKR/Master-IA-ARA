from __future__ import annotations

import csv
import json
from pathlib import Path

from cs2_trend.phase0.repositories import FileCatalogRepository, FileProbeDumpRepository
from cs2_trend.phase0.services import CatalogService, CsfloatCatalogParser


def test_catalog_service_parses_and_persists_tabular_outputs(tmp_path: Path) -> None:
    probe_store = FileProbeDumpRepository(base_dir=tmp_path / "probes")
    catalog_store = FileCatalogRepository(base_dir=tmp_path / "catalog")
    service = CatalogService(
        parser=CsfloatCatalogParser(),
        catalog_store=catalog_store,
        dump_store=probe_store,
    )

    dump_record = probe_store.write_probe_dump(
        source="csfloat",
        endpoint="https://csfloat.com/api/v1/listings",
        run_id="run123",
        status_code=200,
        payload={
            "data": [
                {
                    "id": 101,
                    "market_hash_name": "StatTrak™ AK-47 | Redline (Field-Tested)",
                },
                {
                    "id": "102",
                    "market_hash_name": "Souvenir M4A1-S | Printstream (Factory New)",
                },
            ]
        },
    )

    records = service.build_catalog_from_dump(dump_path=dump_record.dump_path)
    result = service.persist_catalog(
        records=records,
        output_format="both",
        base_name="master_catalog",
    )

    assert len(records) == 2
    assert records[0].canonical_item_id == "ak_47__redline__field_tested__stattrak"
    assert records[1].canonical_item_id == "m4a1_s__printstream__factory_new__souvenir"
    assert result.json_path is not None
    assert result.csv_path is not None

    json_rows = json.loads(result.json_path.read_text(encoding="utf-8"))
    assert isinstance(json_rows, list)
    assert json_rows[0]["canonical_item_id"] == records[0].canonical_item_id

    with result.csv_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)

    assert rows[0]["canonical_item_id"] == records[0].canonical_item_id
    assert "source_keys" in rows[0]
