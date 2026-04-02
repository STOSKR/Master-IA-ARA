# Memoria de Scraping

Este documento registra aprendizaje operativo de largo plazo para el bot de scraping multidominio.

Regla operativa:
- Antes de iniciar cualquier tarea nueva, leer este archivo completo.

Formato de entrada:
- Fecha (UTC)
- Problema
- Investigacion en navegador (agent-browser)
- Solucion tecnica aplicada
- Evidencia (archivos/commits)
- Riesgos pendientes

## Entradas

### 2026-04-01T00:00:00Z - Inicializacion de memoria
- Problema: No existia una memoria persistente para registrar descubrimientos de endpoints, antibot y cambios de acceso.
- Investigacion en navegador (agent-browser): No aplica en esta inicializacion.
- Solucion tecnica aplicada: Se crea este archivo en la raiz para centralizar decisiones y aprendizaje operativo.
- Evidencia (archivos/commits): memoria_scraping.md.
- Riesgos pendientes: Ninguno.

### 2026-04-01T21:00:00Z - CSFloat autenticacion por cookies locales (Opcion B)
- Problema: La validacion previa de Phase 1 exigia `CSFLOAT_API_KEY` o `CSFLOAT_COOKIE` en entorno y no aceptaba cookies de `cookies.json`.
- Investigacion en navegador (agent-browser): Se verifico flujo de autenticacion local y disponibilidad de cookies persistidas para CSFloat.
- Solucion tecnica aplicada: Se modifica el gate de validacion para aceptar encabezado de cookie construido desde archivo local, usando `build_cookie_header_for_platform(platform="csfloat")`.
- Evidencia (archivos/commits): `src/cs2_trend/phase1/connector_setup.py`, `tests/phase1/test_services.py`.
- Riesgos pendientes: Cookie expirada o invalida puede seguir bloqueando extraccion real.

### 2026-04-01T21:30:00Z - Steam endpoint funcional sin login
- Problema: Sin endpoint configurado, la extraccion Steam no podia ejecutarse.
- Investigacion en navegador (agent-browser): En captura HAR se observo `itemordershistogram`; adicionalmente se verifico que la pagina de listing publica incluye `var line1` sin autenticacion.
- Solucion tecnica aplicada: Se fija endpoint por defecto de Steam a plantilla de listing (`https://steamcommunity.com/market/listings/730/{market_hash_name}`) y se implementa resolucion dinamica de URL por item.
- Evidencia (archivos/commits): `src/extraction/connectors/steam.py`, artefacto `data/dumps/probes/endpoint_discovery/steam_har_batch.json`, prueba en `tests/extraction/test_connectors_probe_first.py`.
- Riesgos pendientes: Si Steam cambia el formato `line1`, el fallback HTML requerira ajuste.

### 2026-04-01T21:40:00Z - SteamDT rutas API detectadas y fallback publico
- Problema: Faltaba endpoint configurado y el flujo por item es sensible a bloqueos de entorno.
- Investigacion en navegador (agent-browser): En HAR de home y detalle se detectaron rutas como:
	- `https://api.steamdt.com/index/item-block/v1/summary`
	- `https://api.steamdt.com/user/skin/v1/item` (POST)
	- `https://api.steamdt.com/user/skin/v1/market-comparsion` (GET con `itemId`)
	- `https://api.steamdt.com/user/steam/type-trend/v2/item/details` (POST)
- Solucion tecnica aplicada: Se establece endpoint por defecto publico `index/item-block/v1/summary` y se agrega parser fallback para convertir `data.hot.defaultList` en puntos normalizados.
- Evidencia (archivos/commits): `src/extraction/connectors/steamdt.py`, artefactos `steamdt_har_batch.json` y `steamdt_detail_har_batch.json`.
- Riesgos pendientes: El endpoint de summary no es historico por item; se usa como ruta estable de continuidad mientras se perfecciona mapeo itemId.

### 2026-04-01T22:00:00Z - Buff163 endpoints publicos y restricciones de login
- Problema: No habia endpoint por defecto y se desconocia que datos eran publicos sin sesion.
- Investigacion en navegador (agent-browser): En HAR se detectaron endpoints de goods; se probaron rutas candidatas desde navegador/script.
- Solucion tecnica aplicada:
	- Endpoint por defecto configurado a `https://buff.163.com/api/market/goods/sell_order`.
	- Parser ampliado para `data.items` con campos `created_at` y `price`.
	- Query estandarizada con `game=csgo`, `goods_id`, `page_num`, etc.
	- Se documenta que `price_history` y `bill_order` responden `Login Required` en acceso anonimo.
- Evidencia (archivos/commits): `src/extraction/connectors/buff163.py`, artefactos `buff163_goods_har_batch.json` y `buff163_price_chart_open_batch.json`, prueba en `tests/extraction/test_connectors_probe_first.py`.
- Riesgos pendientes: Sin login no hay historial completo en endpoint de precio; se consume ordenes publicas.

### 2026-04-01T22:10:00Z - CS.Money bloqueado por Cloudflare y fallback simulado
- Problema: CS.Money devuelve challenge de Cloudflare y no expone rutas de datos publicas consumibles sin resolver desafio/sesion.
- Investigacion en navegador (agent-browser): HAR de `https://cs.money/` muestra trafico de `cdn-cgi/challenge-platform` y Turnstile, sin endpoints de historico accesibles.
- Solucion tecnica aplicada:
	- Se configura endpoint por defecto `https://cs.money/`.
	- Se intenta extraccion normal; si hay bloqueo HTTP o shape no soportado, se devuelve bloque simulado determinista (24 puntos, formato canonico) para no colapsar pipeline.
	- Se deja trazabilidad en payload con `simulated=true` y encabezado `x-simulated=true`.
- Evidencia (archivos/commits): `src/extraction/connectors/csmoney.py`, artefacto `csmoney_har_batch.json`, prueba en `tests/extraction/test_connectors_probe_first.py`.
- Riesgos pendientes: Datos simulados no representan mercado real; deben reemplazarse al habilitar sesion real.

### 2026-04-01T22:30:00Z - Inicio de Fase 2: bot multidominio con concurrencia por fuente
- Problema: Se necesitaba un bot que cumpla regla estricta de concurrencia (paralelo entre plataformas y secuencial con delay dentro de cada plataforma).
- Investigacion en navegador (agent-browser): Se uso el aprendizaje previo de endpoints para definir conectores ejecutables por fuente y estrategia de continuidad.
- Solucion tecnica aplicada:
	- Nuevo modulo `src/cs2_trend/phase2/bot.py`.
	- Ejecucion paralela por conector y secuencial por target con `delay_seconds`.
	- Persistencia y validacion reutilizando contrato tabular (raw/curated + shards + metrics).
	- Script operativo `scripts/phase2_multidomain_bot.py`.
- Evidencia (archivos/commits): `src/cs2_trend/phase2/bot.py`, `scripts/phase2_multidomain_bot.py`, `tests/phase2/test_bot.py`.
- Riesgos pendientes: Mapeo de IDs entre catalogo canonico y fuentes externas puede requerir normalizacion adicional para maximizar datos reales por fuente.

### 2026-04-01T22:45:00Z - Continuidad de ejecucion con fallbacks en Buff163 y CSFloat
- Problema: En corrida real del bot, `buff163` y `csfloat` fallaban por combinacion de restricciones de acceso y desalineacion de IDs.
- Investigacion en navegador (agent-browser):
	- Buff163: `sell_order` publico funciona, pero historico completo exige login y el `goods_id` del catalogo no siempre mapea.
	- CSFloat: hay escenarios de auth/shape no compatible segun sesion/estado del endpoint.
- Solucion tecnica aplicada:
	- Se agrega fallback simulado determinista en `Buff163Connector` y `CSFloatConnector` para que el pipeline no colapse.
	- Cada fallback marca `x-simulated=true` y payload con `simulated=true`.
- Evidencia (archivos/commits): `src/extraction/connectors/buff163.py`, `src/extraction/connectors/csfloat.py`, `tests/extraction/test_connectors_probe_first.py`.
- Riesgos pendientes: Requiere futuro reemplazo progresivo por datos 100% reales cuando mapeo de IDs y autenticacion esten consolidados.

### 2026-04-01T22:55:00Z - Leccion de entorno (WSL/uv)
- Problema: El entorno virtual gestionado por uv quedo inconsistente (paquetes con `dist-info` sin modulos importables), bloqueando ejecucion de validaciones.
- Investigacion en navegador (agent-browser): No aplica; diagnostico por inspeccion de site-packages y pruebas de import.
- Solucion tecnica aplicada: Se prioriza un runner de Fase 2 standalone stdlib-only para no depender de librerias inestables del entorno durante la validacion operativa.
- Evidencia (archivos/commits): `scripts/phase2_multidomain_bot.py`, log de ejecucion `/tmp/phase2_bot_run.log`.
- Riesgos pendientes: Saneamiento integral del toolchain uv queda como tarea de hardening de entorno.

### 2026-04-01T23:00:00Z - Validacion operativa completa del bot multidominio
- Problema: Era necesario comprobar que el bot no colapsa y persiste artefactos validos con todas las fuentes.
- Investigacion en navegador (agent-browser): Se contrastaron previamente endpoints y bloqueos por fuente; en corrida final se verifico comportamiento esperado de rutas reales y fallbacks.
- Solucion tecnica aplicada: Ejecucion con `PYTHONPATH=src python3 scripts/phase2_multidomain_bot.py --limit-items 1 --delay-seconds 1 --source steam --source steamdt --source buff163 --source csmoney --source csfloat`.
- Evidencia (archivos/commits): run_id `d992ac0f42ce4f679b26ab8126611a93`, `data/runs/d992ac0f42ce4f679b26ab8126611a93_metrics.json`, salidas raw/curated por fuente en `data/raw` y `data/curated`.
- Riesgos pendientes: Aunque el pipeline completa 5/5, parte de los datos puede provenir de fallbacks simulados cuando una fuente real esta bloqueada.

### 2026-04-02T00:00:00Z - Steam historico completo con endpoint pricehistory
- Problema: La extraccion estaba priorizando HTML/listing y podia devolver serie parcial en lugar de historico completo.
- Investigacion en navegador (agent-browser): Se confirma que el grafico de Steam usa el endpoint `/market/pricehistory` para el historico completo por item.
- Solucion tecnica aplicada:
	- `SteamConnector` cambia a estrategia `pricehistory` por defecto (`appid=730` + `market_hash_name`).
	- Se agrega parser dedicado para shape real `prices: [[timestamp, price, volume], ...]`.
	- Se mantiene fallback automatico a listing (`line1`) si `pricehistory` falla por auth/bloqueo/shape.
- Evidencia (archivos/commits): `src/extraction/connectors/steam.py`, `src/extraction/connectors/steam_pricehistory.py`, `src/cs2_trend/core/config.py`, `tests/extraction/test_connectors_probe_first.py`.
- Riesgos pendientes: Si la sesion Steam expira, `pricehistory` puede degradar a fallback HTML.

### 2026-04-02T00:10:00Z - Validacion visual de sesion con cookies en browser real
- Problema: El browser integrado de VS Code no comparte automaticamente la sesion/cookies capturadas del scraper.
- Investigacion en navegador (agent-browser): Se observa que abrir URL directa no garantiza sesion autenticada en esa vista.
- Solucion tecnica aplicada:
	- Nuevo script `scripts/open_logged_browser.js` para abrir Chromium visible con cookies cargadas desde `cookies.json`/`AUTH_COOKIES_PATH`.
	- `setup_auth.js` ahora imprime comando directo de validacion visual post-captura.
- Evidencia (archivos/commits): `scripts/open_logged_browser.js`, `setup_auth.js`.
- Riesgos pendientes: Cookies invalidas/expiradas seguiran mostrando estado no autenticado y requeriran recaptura.
