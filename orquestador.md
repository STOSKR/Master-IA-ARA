# Instrucciones operativas del orquestador

Eres el agente orquestador principal del proyecto de análisis de Counter-Strike 2. Tu objetivo actual es completar secuencialmente la fase cero y la fase uno del desarrollo. Todo el código y los directorios que generen tus subagentes deben operar en el espacio de usuario estándar, ya que el entorno no cuenta con permisos de administrador.

## Fase cero: creación del catálogo maestro

Antes de extraer historiales de precios, debes instanciar un subagente explorador para construir un catálogo maestro de objetos. Este subagente se conectará a la interfaz de programación de CSFloat para extraer la lista completa de armas, aspectos, estados de desgaste y atributos especiales.

El subagente explorador tiene la obligación de interceptar y comprender la estructura de los paquetes de red en formato JSON que devuelve el servidor. Antes de programar el bucle definitivo, generará un volcado de prueba para inspeccionar las claves y asegurarse de que asimila la información recibida.

## Fase uno: extracción de series temporales

Una vez validado y guardado el catálogo maestro de forma local, debes instanciar la siguiente topología de subagentes:

1. Agentes de extracción: crea un subagente especializado para el mercado de la comunidad de Steam, Steamdt, Buff163, CS.Money y CSFloat. Reparte el catálogo maestro entre ellos. Su tarea es desarrollar secuencias de comandos en Python mediante AsyncIO para descargar el historial de precios.
1. Agentes de revisión de código: por cada archivo generado, instancia un agente revisor que audite el código. Este agente exigirá indicaciones de tipo, validará la arquitectura con Mypy y Ruff, y rechazará cualquier secuencia monolítica.

## Reglas operativas para la extracción

- Comprensión de paquetes: los extractores no deben presuponer la estructura interna de las páginas web. Tienen que programar peticiones de inspección, volcar la respuesta en bruto y analizar el árbol de datos para identificar la ubicación real de los datos temporales.
- Tolerancia a fallos: exige la programación de reintentos y esperas progresivas. Si una petición fracasa repetidamente, el cuerpo de la respuesta se guardará en un directorio local de volcados con una marca de tiempo.
- Comportamiento reactivo: si un subagente no comprende la respuesta, detecta una medida de seguridad o se bloquea, debe detenerse y pedir aclaraciones. Tiene estrictamente prohibido inventar implementaciones alternativas.

## Maintenance Update 2026-03-25

- [x] Step 1 completed: duplicate/unused code cleanup and refactor in scraper-related modules.
- [x] Step 2 completed: live endpoint validation performed, blocking/auth failures reproduced, and scraper hardening applied.
- [x] Step 2 fix applied: CSFloat authentication support added via CSFLOAT_API_KEY or CSFLOAT_COOKIE in Phase 0/Phase 1 paths.
- [ ] Live extraction success against protected CSFloat endpoint remains pending until valid authentication credentials are configured.

## Maintenance Update 2026-04-02

- [x] Steam connector now prioritizes `/market/pricehistory` for full historical series, with listing fallback only when required.
- [x] Browser session validation helper added: `node scripts/open_logged_browser.js --platform steam`.
- [x] Phase 2 final run executed with 5 sources x 5 items (run_id `8479a1df1e614fd1992dc2730199901e`, 25/25 successful jobs).
- [x] JSON shard schema compacted to hierarchical shape (`source -> category -> items -> series`) to reduce redundant rows.

## Maintenance Update 2026-04-02 (Scope Simplification)

- [x] Source scope narrowed to Steam, SteamDT, Buff163 by default (`phase1 extract` and standalone bot defaults).
- [x] Historical outputs and metrics from non-target sources removed from `data/raw`, `data/curated`, and `data/runs`.
- [x] Full catalog run completed for SteamDT (`run_id=a454d6e856e3493c94a23e3605e977fd`, 25841/25841 successful jobs).
- [ ] Full catalog run for Steam remains constrained by platform throttling (HTTP 429 under sustained load) and requires extended throttled execution windows.

## Next Development Steps

1. Configure CSFLOAT_API_KEY or CSFLOAT_COOKIE in runtime environment.
1. Re-run phase0 probe and phase1 extraction using authenticated session.
1. Validate persisted raw/curated outputs and metrics artifacts in data directories.
1. Continue with Phase 2 windowing implementation once authenticated extraction is stable.
