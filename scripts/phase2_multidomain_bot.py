from __future__ import annotations

import argparse
import asyncio
import csv
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from extraction.connectors.buff163 import Buff163Connector
from extraction.connectors.csfloat import CSFloatConnector
from extraction.connectors.csmoney import CSMoneyConnector
from extraction.connectors.steam import SteamConnector
from extraction.connectors.steamdt import SteamdtConnector
from extraction.models import ExtractionTarget
from extraction.protocols import HttpResponse


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run multidomain scraping bot with per-source sequential access."
    )
    parser.add_argument(
        "--source",
        dest="sources",
        action="append",
        default=[],
        help="Data source to include (repeatable). Defaults to all sources.",
    )
    parser.add_argument(
        "--limit-items",
        type=int,
        default=20,
        help="Maximum number of catalog items to process.",
    )
    parser.add_argument(
        "--catalog-file",
        type=Path,
        default=Path("data/catalog/master_catalog_exhaustive.json"),
        help="Optional catalog JSON/CSV path.",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=2.0,
        help=(
            "Delay between consecutive requests to the same source. "
            "Different sources still run in parallel."
        ),
    )
    parser.add_argument(
        "--max-json-rows",
        type=int,
        default=2000,
        help="Maximum rows per JSON shard file.",
    )
    return parser


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    data_dir: Path = Path("data")
    raw_dir: Path = Path("data/raw")
    curated_dir: Path = Path("data/curated")
    dump_dir: Path = Path("data/dumps")
    timeout_seconds: float = 20.0


class StdlibAsyncHttpClient:
    """Async wrapper over urllib for connector compatibility without third-party deps."""

    def __init__(self, *, timeout_seconds: float) -> None:
        self._timeout_seconds = timeout_seconds

    async def get(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> HttpResponse:
        return await asyncio.to_thread(
            self._sync_get,
            url,
            params,
            headers,
        )

    async def aclose(self) -> None:
        return None

    def _sync_get(
        self,
        url: str,
        params: Mapping[str, str] | None,
        headers: Mapping[str, str] | None,
    ) -> HttpResponse:
        final_url = url
        if params:
            query = urlencode({key: value for key, value in params.items() if value is not None})
            joiner = "&" if "?" in url else "?"
            final_url = f"{url}{joiner}{query}"

        request = Request(final_url, method="GET")
        for key, value in (headers or {}).items():
            request.add_header(key, value)

        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                return HttpResponse(
                    url=final_url,
                    status_code=response.status,
                    headers=dict(response.headers.items()),
                    body=response.read(),
                )
        except HTTPError as exc:
            body = exc.read() if exc.fp is not None else b""
            return HttpResponse(
                url=final_url,
                status_code=exc.code,
                headers=dict(exc.headers.items()) if exc.headers else {},
                body=body,
            )
        except URLError as exc:
            message = str(exc).encode("utf-8", errors="ignore")
            return HttpResponse(
                url=final_url,
                status_code=599,
                headers={},
                body=message,
            )


async def _run(args: argparse.Namespace) -> None:
    runtime = RuntimeConfig()
    _ensure_dirs(runtime)

    selected_sources = args.sources or ["steam", "steamdt", "buff163", "csmoney", "csfloat"]
    selected_sources = _normalize_sources(selected_sources)

    targets = _load_targets(args.catalog_file, args.limit_items)
    run_id = uuid4().hex
    started_at = datetime.now(tz=UTC)

    client = StdlibAsyncHttpClient(timeout_seconds=runtime.timeout_seconds)
    try:
        connectors = _build_connectors(client=client, selected_sources=selected_sources)
        results = await _run_sources_parallel(
            connectors=connectors,
            targets=targets,
            delay_seconds=args.delay_seconds,
        )
    finally:
        await client.aclose()

    raw_rows = _build_rows(results)
    curated_rows = _curate_rows(raw_rows)

    timestamp = datetime.now(tz=UTC)
    raw_paths = _write_rows_by_source_csv(runtime.raw_dir, run_id, timestamp, raw_rows, "historical_prices_raw.csv")
    curated_paths = _write_rows_by_source_csv(
        runtime.curated_dir,
        run_id,
        timestamp,
        curated_rows,
        "historical_prices_curated.csv",
    )
    raw_json_paths = _write_json_shards(
        runtime.raw_dir,
        run_id,
        timestamp,
        raw_rows,
        "historical_prices_raw",
        args.max_json_rows,
    )
    curated_json_paths = _write_json_shards(
        runtime.curated_dir,
        run_id,
        timestamp,
        curated_rows,
        "historical_prices_curated",
        args.max_json_rows,
    )

    success_count = sum(1 for item in results if item["success"])  # type: ignore[index]
    failure_count = len(results) - success_count
    metrics_path = _write_metrics(
        data_dir=runtime.data_dir,
        run_id=run_id,
        started_at=started_at,
        finished_at=datetime.now(tz=UTC),
        results=results,
    )

    print(
        "Phase2 bot completed: "
        f"run_id={run_id} jobs={len(results)} "
        f"success={success_count} failure={failure_count} "
        f"raw_rows={len(raw_rows)}"
    )
    print(f"- metrics: {metrics_path}")
    for path in raw_paths:
        print(f"- raw: {path}")
    for path in raw_json_paths:
        print(f"- raw_json: {path}")
    for path in curated_paths:
        print(f"- curated: {path}")
    for path in curated_json_paths:
        print(f"- curated_json: {path}")


def _ensure_dirs(runtime: RuntimeConfig) -> None:
    runtime.data_dir.mkdir(parents=True, exist_ok=True)
    runtime.raw_dir.mkdir(parents=True, exist_ok=True)
    runtime.curated_dir.mkdir(parents=True, exist_ok=True)
    runtime.dump_dir.mkdir(parents=True, exist_ok=True)


def _normalize_sources(sources: Sequence[str]) -> list[str]:
    allowed = {"steam", "steamdt", "buff163", "csmoney", "csfloat"}
    normalized: list[str] = []
    for source in sources:
        current = source.strip().lower()
        if current and current in allowed and current not in normalized:
            normalized.append(current)
    return normalized


def _load_targets(catalog_file: Path, limit_items: int) -> list[ExtractionTarget]:
    payload = json.loads(catalog_file.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Catalog JSON must contain a list")

    targets: list[ExtractionTarget] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        canonical_item_id = _as_str(row.get("canonical_item_id"))
        if canonical_item_id is None:
            continue

        source_keys = row.get("source_keys") if isinstance(row.get("source_keys"), dict) else {}
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}

        market_hash_name = (
            _as_str(metadata.get("raw_market_name"))
            or _as_str(row.get("market_hash_name"))
            or _as_str(row.get("item_name"))
            or canonical_item_id
        )
        item_id = (
            _as_str(source_keys.get("csfloat"))
            or _as_str(row.get("listing_id"))
            or canonical_item_id
        )

        context: dict[str, object] = {
            "canonical_item_id": canonical_item_id,
            "object_type": _as_str(row.get("object_type")),
            "object_subtype": _as_str(row.get("object_subtype")),
            "type_name": _as_str(row.get("type_name")),
            "currency": "USD",
        }

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
        raise ValueError("No valid targets found in catalog")
    return targets


def _build_connectors(*, client: StdlibAsyncHttpClient, selected_sources: Sequence[str]) -> list[object]:
    connector_map = {
        "steam": SteamConnector(http_client=client),
        "steamdt": SteamdtConnector(http_client=client),
        "buff163": Buff163Connector(http_client=client),
        "csmoney": CSMoneyConnector(http_client=client),
        "csfloat": CSFloatConnector(http_client=client),
    }
    return [connector_map[source] for source in selected_sources if source in connector_map]


async def _run_sources_parallel(
    *,
    connectors: Sequence[object],
    targets: Sequence[ExtractionTarget],
    delay_seconds: float,
) -> list[dict[str, object]]:
    tasks = [
        asyncio.create_task(
            _run_source_sequential(
                connector=connector,
                targets=targets,
                delay_seconds=delay_seconds,
            )
        )
        for connector in connectors
    ]
    grouped = await asyncio.gather(*tasks)
    return [row for rows in grouped for row in rows]


async def _run_source_sequential(
    *,
    connector: object,
    targets: Sequence[ExtractionTarget],
    delay_seconds: float,
) -> list[dict[str, object]]:
    source_results: list[dict[str, object]] = []
    source_name = str(getattr(connector, "source_name", "unknown"))

    for index, target in enumerate(targets):
        started_at = datetime.now(tz=UTC)
        try:
            extraction = await connector.extract(target)  # type: ignore[attr-defined]
            source_results.append(
                {
                    "source": source_name,
                    "target": target,
                    "success": True,
                    "started_at": started_at,
                    "finished_at": datetime.now(tz=UTC),
                    "extraction": extraction,
                    "error_type": None,
                    "error_message": None,
                }
            )
        except Exception as exc:  # noqa: BLE001
            source_results.append(
                {
                    "source": source_name,
                    "target": target,
                    "success": False,
                    "started_at": started_at,
                    "finished_at": datetime.now(tz=UTC),
                    "extraction": None,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                }
            )

        if delay_seconds > 0 and index < len(targets) - 1:
            await asyncio.sleep(delay_seconds)

    return source_results


def _build_rows(results: Sequence[dict[str, object]]) -> list[dict[str, object | None]]:
    rows: list[dict[str, object | None]] = []
    for result in results:
        if not bool(result["success"]):
            continue
        extraction = result["extraction"]
        if extraction is None:
            continue

        target = extraction.target
        canonical_item_id = _as_str(target.context.get("canonical_item_id")) or target.item_id
        for point in extraction.points:
            price = float(point.price)
            if not math.isfinite(price) or price <= 0:
                continue
            rows.append(
                {
                    "timestamp_utc": point.timestamp.astimezone(UTC).isoformat(),
                    "source": extraction.source_name,
                    "canonical_item_id": canonical_item_id,
                    "price": price,
                    "currency": point.currency.strip().upper(),
                    "price_basis": "listing",
                    "volume": float(point.volume) if point.volume is not None else None,
                    "availability": None,
                    "object_type": _as_str(target.context.get("object_type")),
                    "object_subtype": _as_str(target.context.get("object_subtype")),
                    "type_name": _as_str(target.context.get("type_name")),
                }
            )

    rows.sort(
        key=lambda row: (
            str(row.get("timestamp_utc")),
            str(row.get("source")),
            str(row.get("canonical_item_id")),
        )
    )
    return rows


def _curate_rows(rows: Sequence[dict[str, object | None]]) -> list[dict[str, object | None]]:
    deduped: list[dict[str, object | None]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for row in rows:
        key = (
            str(row.get("timestamp_utc")),
            str(row.get("source")),
            str(row.get("canonical_item_id")),
            str(row.get("currency")),
            str(row.get("price_basis")),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(dict(row))

    return deduped


def _write_rows_by_source_csv(
    root_dir: Path,
    run_id: str,
    timestamp: datetime,
    rows: Sequence[dict[str, object | None]],
    file_name: str,
) -> list[Path]:
    grouped: dict[str, list[dict[str, object | None]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("source")), []).append(row)

    paths: list[Path] = []
    for source, source_rows in sorted(grouped.items()):
        target_dir = _partition_dir(root_dir, timestamp, source, run_id)
        output_path = target_dir / file_name
        fieldnames = list(source_rows[0].keys())
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(source_rows)
        paths.append(output_path)
    return paths


def _write_json_shards(
    root_dir: Path,
    run_id: str,
    timestamp: datetime,
    rows: Sequence[dict[str, object | None]],
    prefix: str,
    max_json_rows: int,
) -> list[Path]:
    grouped: dict[tuple[str, str], list[dict[str, object | None]]] = {}
    for row in rows:
        source = str(row.get("source"))
        object_type = str(row.get("object_type") or "unknown")
        grouped.setdefault((source, object_type), []).append(row)

    paths: list[Path] = []
    for (source, object_type), source_rows in sorted(grouped.items()):
        target_dir = _partition_dir(root_dir, timestamp, source, run_id)
        shard_dir = target_dir / f"category={_slug(object_type)}"
        shard_dir.mkdir(parents=True, exist_ok=True)

        for shard_index, start in enumerate(range(0, len(source_rows), max_json_rows), start=1):
            chunk = source_rows[start : start + max_json_rows]
            output_path = shard_dir / f"{prefix}_part_{shard_index:04d}.json"
            output_path.write_text(json.dumps(chunk, indent=2, ensure_ascii=True), encoding="utf-8")
            paths.append(output_path)

    return paths


def _write_metrics(
    *,
    data_dir: Path,
    run_id: str,
    started_at: datetime,
    finished_at: datetime,
    results: Sequence[dict[str, object]],
) -> Path:
    per_source: dict[str, dict[str, int]] = {}
    for result in results:
        source = str(result.get("source"))
        stats = per_source.setdefault(source, {"success_count": 0, "failure_count": 0})
        if bool(result.get("success")):
            stats["success_count"] += 1
        else:
            stats["failure_count"] += 1

    payload = {
        "run_id": run_id,
        "started_at_utc": started_at.isoformat(),
        "finished_at_utc": finished_at.isoformat(),
        "duration_seconds": (finished_at - started_at).total_seconds(),
        "total_jobs": len(results),
        "success_count": sum(1 for result in results if bool(result.get("success"))),
        "failure_count": sum(1 for result in results if not bool(result.get("success"))),
        "sources": per_source,
    }

    runs_dir = data_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = runs_dir / f"{run_id}_metrics.json"
    metrics_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return metrics_path


def _partition_dir(root_dir: Path, timestamp: datetime, source: str, run_id: str) -> Path:
    date_partition = timestamp.date().isoformat()
    path = root_dir / f"date={date_partition}" / f"source={source}" / f"run={run_id}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _slug(value: str) -> str:
    chars = []
    for char in value.lower().strip():
        if char.isalnum() or char in {"-", "_"}:
            chars.append(char)
        else:
            chars.append("-")
    slug = "".join(chars).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "unknown"


def _as_str(value: object | None) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, int):
        return str(value)
    return None


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
