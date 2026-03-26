# INTEGRATIONS

## External market sources

- Steam Community Market via extraction/connectors/steam.py.
- SteamDT via extraction/connectors/steamdt.py.
- Buff163 via extraction/connectors/buff163.py.
- CS.Money via extraction/connectors/csmoney.py.
- CSFloat via extraction/connectors/csfloat.py.

## Endpoint configuration model

- Each connector supports explicit endpoint injection in constructor.
- If not provided, endpoint is loaded from source-specific environment variable.
- Missing endpoint raises EndpointNotConfiguredError before probing.

## Authentication and request headers

- Buff163 connector supports BUFF163_COOKIE and BUFF163_USER_AGENT header injection.
- CSFloat connector supports CSFLOAT_API_KEY as Authorization header.
- CSMoney connector supports CSMONEY_AUTH_TOKEN as Bearer token.
- Steam and SteamDT connectors currently rely on public-style request parameters.

## Query contracts per source

- Steam/SteamDT/CSFloat use market_hash_name and item_id style params.
- Buff163 adds goods_id plus market_hash_name.
- CSMoney uses name plus item_id.
- Contracts are centralized per connector through build_query_params.

## HTTP client integrations

- extraction/http.py: HttpxAsyncClient wraps httpx.AsyncClient into AsyncHttpClient protocol.
- cs2_trend/phase0/http_clients.py: UrllibJsonHttpClient wraps urllib in async thread bridge.
- Phase 0 currently probes CSFloat through urllib-based client.

## Data shape integration strategy

- Connectors use build_json_point_parser with multiple JsonShapeSpec alternatives.
- Each source lists accepted payload layouts to tolerate endpoint drift.
- Unknown response structures raise UnknownResponseShapeError.

## Retry and failure persistence integration

- extraction/retry.py wraps connector calls with exponential backoff and jitter support.
- On repeated failures, anomaly dumps are persisted with source/item metadata.
- cs2_trend/phase0/services.py also captures fallback dumps on probe failures.

## Filesystem as integration boundary

- Probe records and catalog artifacts are persisted as JSON/CSV in local directories.
- No database integration exists yet.
- No message queue or streaming integration exists yet.

## Current integration status

- Implemented end-to-end path: csfloat probe -> dump -> catalog parse -> JSON/CSV outputs.
- Other connectors are implemented at extraction package level and testable via kernel.
- Full production extraction workflow from CLI phase1 command is not wired yet.

## Integration risks to monitor

- External APIs can change payload shape despite multi-shape parser support.
- Auth-sensitive sources (Buff163, CSMoney) depend on external credential freshness.
- Connector behavior currently assumes JSON-like payloads for historical points.

## Maintenance Update 2026-03-25

- [x] Step 1 completed: duplicate/unused code cleanup and refactor in scraper-related modules.
- [x] Step 2 completed: live endpoint validation performed, blocking/auth failures reproduced, and scraper hardening applied.
- [x] Step 2 fix applied: CSFloat authentication support added via CSFLOAT_API_KEY or CSFLOAT_COOKIE in Phase 0/Phase 1 paths.
- [ ] Live extraction success against protected CSFloat endpoint remains pending until valid authentication credentials are configured.

## Next Development Steps

1. Configure CSFLOAT_API_KEY or CSFLOAT_COOKIE in runtime environment.
1. Re-run phase0 probe and phase1 extraction using authenticated session.
1. Validate persisted raw/curated outputs and metrics artifacts in data directories.
1. Continue with Phase 2 windowing implementation once authenticated extraction is stable.
