from __future__ import annotations

import json
from pathlib import Path

from cs2_trend.phase0.repositories import FileProbeDumpRepository


def test_probe_dump_write_and_read_payload(tmp_path: Path) -> None:
    repository = FileProbeDumpRepository(base_dir=tmp_path)

    record = repository.write_probe_dump(
        source="csfloat",
        endpoint="https://csfloat.com/api/v1/listings",
        run_id="run123",
        status_code=200,
        payload={"data": [{"id": 1, "market_hash_name": "AK-47 | Redline (Field-Tested)"}]},
    )

    assert record.dump_path.exists()
    assert record.dump_path.suffix == ".json"

    raw_document = json.loads(record.dump_path.read_text(encoding="utf-8"))
    assert raw_document["source"] == "csfloat"
    assert raw_document["status_code"] == 200
    assert "captured_at_utc" in raw_document

    payload = repository.read_probe_payload(path=record.dump_path)
    assert isinstance(payload, dict)
    assert payload["data"][0]["id"] == 1
