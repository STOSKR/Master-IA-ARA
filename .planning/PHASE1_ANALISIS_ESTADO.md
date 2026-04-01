# Fase 1 - Analisis y Reporte de Estado

Fecha: 2026-04-01

## Alcance revisado

Se revisaron todos los archivos en `.planning` y el estado real de implementacion en codigo para validar:

1. Campos definidos por web para scraping.
2. Transformadores/validadores de datos.
3. Estado de cookies de sesion y su accesibilidad.

Tambien se comprobo disponibilidad de herramientas solicitadas por el flujo:

- `agent-browser`: disponible en PATH.
- `gsd`: no disponible en PATH de la terminal actual.

## Fuentes de evidencia revisadas

- Planificacion: `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md`, `.planning/PROJECT.md`, `.planning/PHASES_V2_TO_V6.md`, `.planning/config.json`.
- Conectores y parsing: `src/extraction/connectors/*.py`, `src/extraction/models.py`, `src/extraction/protocols.py`, `src/extraction/cleaning.py`.
- Orquestacion phase1: `src/cs2_trend/phase1/*.py`, `src/cs2_trend/cli.py`.
- Calidad tabular: `src/cs2_price_trend/quality/*.py`.
- Autenticacion/cookies: `src/extraction/auth_cookies.py`, `setup_auth.js`, `cookies.json`.
- Evidencia de dumps: `data/dumps/`.

## Estado por requisito solicitado

### 1) Campos definidos para scrapear por web

### Steam

- Estado: Parcialmente listo.
- Definicion tecnica:
  - Query params: `market_hash_name`, `item_id`.
  - Soporta JSON (`prices`, `history`) y fallback HTML inline `line1`.
- Gap:
  - No hay endpoint de Steam configurado en entorno (`STEAM_PROBE_ENDPOINT` ausente).

### SteamDT

- Estado: Parcialmente listo.
- Definicion tecnica:
  - Query params: `market_hash_name`, `item_id`.
  - Shapes JSON declarados: `data.history`, `history`.
- Gap:
  - No endpoint configurado (`STEAMDT_PROBE_ENDPOINT` ausente).
  - Sin evidencia reciente de probe persistida para validar shape real en este entorno.

### Buff163

- Estado: Parcialmente listo.
- Definicion tecnica:
  - Query params: `goods_id`, `market_hash_name`.
  - Shapes JSON declarados: `data.items`, `items`.
  - Soporte de cookie header desde env o `cookies.json`.
- Gap:
  - No endpoint configurado (`BUFF163_PROBE_ENDPOINT` ausente).

### CS.Money

- Estado: No listo (bloqueado).
- Definicion tecnica:
  - Query params: `name`, `item_id`.
  - Shapes JSON declarados: `history`, `data.history`.
  - Soporte auth por token (`CSMONEY_AUTH_TOKEN`).
- Gap:
  - No endpoint configurado (`CSMONEY_PROBE_ENDPOINT` ausente).
  - No token de autenticacion configurado (`CSMONEY_AUTH_TOKEN` ausente).

### CSFloat

- Estado: Parcialmente listo, bloqueado por autenticacion efectiva.
- Definicion tecnica:
  - Endpoint por defecto en config: `https://csfloat.com/api/v1/listings`.
  - Shapes JSON declarados para `data`/`history` con `created_at` o `timestamp`.
  - Conector soporta `Authorization` (`CSFLOAT_API_KEY`) y cookie (`CSFLOAT_COOKIE` o archivo de cookies).
- Gap critico:
  - Validacion previa de `phase1` exige `CSFLOAT_API_KEY` o `CSFLOAT_COOKIE` en variables de entorno.
  - Aunque existe `cookies.json` con cookies de CSFloat, la prevalidacion no lo considera suficiente para pasar gate de ejecucion.

### 2) Transformadores de datos

- Estado global: Listo (base robusta).
- Evidencia:
  - Transformacion a contrato canonico: `extraction_results_to_history_frame`.
  - Validacion Pandera de esquema historico: `validate_history_dataframe`.
  - Normalizacion/saneamiento inicial: limpieza de puntos, deduplicacion, IQR outlier sanitation.
  - Persistencia estructurada en `data/raw` y `data/curated` por fuente con CSV/JSON shard.
- Observacion:
  - Hay cobertura de pruebas para pipeline phase1, pero cobertura directa de conectores esta mas fuerte en Steam/CSFloat que en SteamDT/Buff163/CS.Money.

### 3) Cookies de sesion guardadas y accesibles

- Estado global: Parcial.
- `cookies.json` contiene cookies para:
  - Steam (8 cookies)
  - CSFloat (7 cookies)
  - Buff163 (14 cookies)
- No hay cookies guardadas para:
  - SteamDT
  - CS.Money
- Accesibilidad tecnica:
  - `auth_cookies.py` puede resolver desde `AUTH_COOKIES_PATH` o fallback a `cookies.json` local.
  - Steam/Buff163/CSFloat pueden construir header desde archivo si no hay env.
  - En phase1, CSFloat queda bloqueado por validacion de prerequisitos porque se exige env var explicita (`CSFLOAT_API_KEY` o `CSFLOAT_COOKIE`).

## Validacion de configuracion de entorno (ejecucion real)

Variables verificadas como no configuradas en este entorno:

- `STEAM_PROBE_ENDPOINT`
- `STEAMDT_PROBE_ENDPOINT`
- `BUFF163_PROBE_ENDPOINT`
- `CSMONEY_PROBE_ENDPOINT`
- `CSFLOAT_PROBE_ENDPOINT`
- `CSFLOAT_API_KEY`
- `CSFLOAT_COOKIE`
- `STEAM_COOKIE`
- `BUFF163_COOKIE`
- `CSMONEY_AUTH_TOKEN`
- `AUTH_COOKIES_PATH`

Nota: aunque `CSFLOAT_PROBE_ENDPOINT` no esta en entorno, existe default en `AppConfig`; el bloqueo real permanece en autenticacion.

## Estado de preparacion consolidado

| Plataforma | Campos parser | Transformadores | Cookies/Auth | Endpoint | Estado |
|---|---|---|---|---|---|
| Steam | Definidos | Compatible | Cookie disponible en archivo | Falta config | Parcial |
| SteamDT | Definidos | Compatible | No requerido/documentado | Falta config | Parcial |
| Buff163 | Definidos | Compatible | Cookie disponible en archivo | Falta config | Parcial |
| CS.Money | Definidos | Compatible | Token ausente | Falta config | Bloqueado |
| CSFloat | Definidos | Compatible | Cookie en archivo, pero gate exige env | Endpoint default existe | Bloqueado |

## Bloqueos criticos detectados

1. No hay endpoints operativos configurados para Steam, SteamDT, Buff163 y CS.Money.
2. CS.Money no tiene token de autenticacion configurado.
3. CSFloat no tiene `CSFLOAT_API_KEY` ni `CSFLOAT_COOKIE` en entorno; con la validacion actual no basta el `cookies.json`.
4. No hay evidencia de probe reciente para SteamDT/Buff163/CS.Money en `data/dumps/probes/`.
5. `gsd` no esta disponible en PATH de terminal, aunque se solicitaba su uso directo.

## Decision de fase

Fase 1 completada como analisis/reporte.

Se detecta informacion critica faltante para pasar a implementacion/ejecucion multidominio completa. Por regla del flujo, se debe detener aqui hasta recibir configuracion faltante o ajuste de criterio de autenticacion para CSFloat.
