"""Business services for phase 0 probing and canonical catalog generation."""

from __future__ import annotations

import re
from pathlib import Path

from cs2_trend.core.dumps import dump_anomalous_response
from cs2_trend.core.retry import RetryPolicy, run_with_retry
from cs2_trend.domain.canonical_id import build_canonical_item_id
from cs2_trend.domain.models import CanonicalItem, MarketSource
from cs2_trend.phase0.interfaces import CatalogParser, CatalogStore, JsonHttpClient, ProbeDumpStore
from cs2_trend.phase0.models import (
    CatalogOutputFormat,
    CatalogPersistenceResult,
    HttpJsonResponse,
    JsonValue,
    ProbeRecord,
)

_STAT_TRACK_PREFIX = re.compile(r"^StatTrak(?:™)?\s+", re.IGNORECASE)
_SOUVENIR_PREFIX = re.compile(r"^Souvenir\s+", re.IGNORECASE)
_WEAR_SUFFIX = re.compile(r"\(([^()]+)\)\s*$")


class CsfloatProbeService:
    """Coordinates CSFloat probing with retries and local dump persistence."""

    def __init__(
        self,
        *,
        http_client: JsonHttpClient,
        dump_store: ProbeDumpStore,
        fallback_dump_dir: Path,
        retry_policy: RetryPolicy,
    ) -> None:
        self._http_client = http_client
        self._dump_store = dump_store
        self._fallback_dump_dir = fallback_dump_dir
        self._retry_policy = retry_policy

    async def capture_sample(self, *, endpoint: str, run_id: str) -> ProbeRecord:
        """Probe endpoint with retries and persist successful payload dump."""

        async def operation() -> HttpJsonResponse:
            return await self._http_client.fetch_json(endpoint=endpoint)

        try:
            response = await run_with_retry(operation, self._retry_policy)
        except Exception as exc:
            fallback_path = dump_anomalous_response(
                base_dir=self._fallback_dump_dir,
                source="csfloat",
                endpoint=endpoint,
                run_id=run_id,
                body=str(exc),
            )
            raise RuntimeError(
                f"probe failed after retries; fallback dump={fallback_path}"
            ) from exc

        return self._dump_store.write_probe_dump(
            source="csfloat",
            endpoint=endpoint,
            run_id=run_id,
            status_code=response.status_code,
            payload=response.payload,
        )

    async def capture_samples(
        self,
        *,
        endpoint: str,
        run_id: str,
        sample_size: int,
    ) -> tuple[ProbeRecord, ...]:
        """Capture one or more probe samples sequentially."""

        if sample_size < 1:
            raise ValueError("sample_size must be >= 1")

        records: list[ProbeRecord] = []
        for _ in range(sample_size):
            record = await self.capture_sample(endpoint=endpoint, run_id=run_id)
            records.append(record)
        return tuple(records)


class CsfloatCatalogParser(CatalogParser):
    """Parse CSFloat payloads into canonical item records."""

    _NAME_KEYS: tuple[str, ...] = (
        "market_hash_name",
        "item_name",
        "name",
        "marketName",
    )
    _ID_KEYS: tuple[str, ...] = (
        "id",
        "listing_id",
        "asset_id",
        "item_id",
    )

    def parse_catalog_items(self, *, payload: JsonValue) -> tuple[CanonicalItem, ...]:
        """Convert raw payload into sorted, deduplicated canonical records."""

        listings = self._extract_listings(payload)
        by_canonical_id: dict[str, CanonicalItem] = {}

        for listing in listings:
            market_name = self._get_first_string(listing, self._NAME_KEYS)
            if market_name is None:
                continue

            parsed = self._parse_market_name(market_name)
            canonical_id = build_canonical_item_id(
                weapon=parsed.weapon,
                skin_name=parsed.skin_name,
                wear=parsed.wear,
                is_stattrak=parsed.is_stattrak,
                is_souvenir=parsed.is_souvenir,
            )

            source_keys: dict[MarketSource, str] = {}
            source_key = self._get_first_string(listing, self._ID_KEYS)
            if source_key is not None:
                source_keys["csfloat"] = source_key

            candidate = CanonicalItem(
                canonical_item_id=canonical_id,
                weapon=parsed.weapon,
                skin_name=parsed.skin_name,
                wear=parsed.wear,
                is_stattrak=parsed.is_stattrak,
                is_souvenir=parsed.is_souvenir,
                source_keys=source_keys,
                metadata={"raw_market_name": market_name},
            )

            existing = by_canonical_id.get(canonical_id)
            if existing is None:
                by_canonical_id[canonical_id] = candidate
            else:
                merged_source_keys = dict(existing.source_keys)
                merged_source_keys.update(candidate.source_keys)
                by_canonical_id[canonical_id] = existing.model_copy(
                    update={"source_keys": merged_source_keys}
                )

        return tuple(sorted(by_canonical_id.values(), key=lambda item: item.canonical_item_id))

    def _extract_listings(self, payload: JsonValue) -> tuple[dict[str, JsonValue], ...]:
        if isinstance(payload, list):
            return tuple(item for item in payload if isinstance(item, dict))

        if isinstance(payload, dict):
            for key in ("data", "items", "results", "listings"):
                value = payload.get(key)
                if isinstance(value, list):
                    return tuple(item for item in value if isinstance(item, dict))

            for value in payload.values():
                extracted = self._extract_listings(value)
                if extracted:
                    return extracted

        return ()

    def _get_first_string(self, listing: dict[str, JsonValue], keys: tuple[str, ...]) -> str | None:
        for key in keys:
            value = listing.get(key)
            if isinstance(value, str):
                cleaned = value.strip()
                if cleaned:
                    return cleaned
            if isinstance(value, int):
                return str(value)
        return None

    def _parse_market_name(self, market_name: str) -> _ParsedMarketName:
        candidate = market_name.strip()
        is_stattrak = False
        is_souvenir = False

        stattrak_match = _STAT_TRACK_PREFIX.match(candidate)
        if stattrak_match is not None:
            is_stattrak = True
            candidate = candidate[stattrak_match.end() :].strip()

        souvenir_match = _SOUVENIR_PREFIX.match(candidate)
        if souvenir_match is not None:
            is_souvenir = True
            candidate = candidate[souvenir_match.end() :].strip()

        wear: str | None = None
        wear_match = _WEAR_SUFFIX.search(candidate)
        if wear_match is not None:
            wear = wear_match.group(1).strip()
            candidate = candidate[: wear_match.start()].strip()

        if "|" in candidate:
            weapon_part, skin_part = candidate.split("|", maxsplit=1)
            weapon = weapon_part.strip()
            skin_name = skin_part.strip()
        else:
            weapon = candidate
            skin_name = candidate

        return _ParsedMarketName(
            weapon=weapon,
            skin_name=skin_name,
            wear=wear,
            is_stattrak=is_stattrak,
            is_souvenir=is_souvenir,
        )


class CatalogService:
    """Application service for building and persisting canonical catalog outputs."""

    def __init__(
        self,
        *,
        parser: CatalogParser,
        catalog_store: CatalogStore,
        dump_store: ProbeDumpStore,
    ) -> None:
        self._parser = parser
        self._catalog_store = catalog_store
        self._dump_store = dump_store

    def build_catalog_from_payload(self, *, payload: JsonValue) -> tuple[CanonicalItem, ...]:
        """Build canonical catalog records from a payload object."""

        return self._parser.parse_catalog_items(payload=payload)

    def build_catalog_from_dump(self, *, dump_path: Path) -> tuple[CanonicalItem, ...]:
        """Load a probe dump and parse canonical catalog records."""

        payload = self._dump_store.read_probe_payload(path=dump_path)
        return self.build_catalog_from_payload(payload=payload)

    def latest_probe_path(self, *, source: str) -> Path | None:
        """Return latest available probe dump path for a source."""

        return self._dump_store.latest_probe_path(source=source)

    def persist_catalog(
        self,
        *,
        records: tuple[CanonicalItem, ...],
        output_format: CatalogOutputFormat,
        base_name: str,
    ) -> CatalogPersistenceResult:
        """Persist canonical records in configured output format."""

        return self._catalog_store.persist_catalog(
            records=records,
            output_format=output_format,
            base_name=base_name,
        )


class _ParsedMarketName:
    """Internal parsed representation of CS item naming conventions."""

    def __init__(
        self,
        *,
        weapon: str,
        skin_name: str,
        wear: str | None,
        is_stattrak: bool,
        is_souvenir: bool,
    ) -> None:
        self.weapon = weapon
        self.skin_name = skin_name
        self.wear = wear
        self.is_stattrak = is_stattrak
        self.is_souvenir = is_souvenir