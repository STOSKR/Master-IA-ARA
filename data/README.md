# Data Outputs

This directory stores extraction artifacts by date/source/run.

## Why `part_0001`, `part_0002`, etc.

JSON outputs are sharded to avoid very large files.

- Control flag: `--max-json-rows`
- Current behavior: this limit is the maximum number of historical points per JSON file.
- If one source/category exceeds that limit, additional files are created: `part_0002`, `part_0003`, and so on.

To reduce splitting, run with a higher limit, for example:

```bash
PYTHONPATH=src python3 scripts/phase2_multidomain_bot.py \
  --limit-items 5 \
  --max-json-rows 50000 \
  --source steam --source steamdt --source buff163 --source csmoney --source csfloat
```

Current simplified scope:

- `steam`
- `steamdt`
- `buff163`

Primary completed full-catalog run in this scope:

- `steamdt` full catalog run_id: `a454d6e856e3493c94a23e3605e977fd`

## Compact JSON Schema

`historical_prices_*_part_XXXX.json` now uses a compact hierarchical schema:

```json
{
  "source": "steam",
  "category": "agent",
  "run_id": "...",
  "kind": "curated",
  "part": 1,
  "item_count": 5,
  "point_count": 12833,
  "items": [
    {
      "type": "agent",
      "name": "1st Lieutenant Farlow | SWAT",
      "canonical_item_id": "agent__1st_lieutenant_farlow_swat",
      "currency": "USD",
      "series": [
        {
          "timestamp": "2026-04-02T06:00:00+00:00",
          "price": 23.08,
          "volume": 11.0
        }
      ]
    }
  ]
}
```

CSV outputs remain tabular for compatibility:

- `historical_prices_raw.csv`
- `historical_prices_curated.csv`
