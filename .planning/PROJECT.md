# CS2 Price Trend Intelligence

## What This Is

Sistema automatizado de uso interno para reconocer y predecir tendencias de precios en objetos digitales de Counter-Strike 2. El producto recopila series temporales históricas desde múltiples mercados y clasifica la tendencia futura de cada activo como alcista, bajista o neutral en una ventana temporal definida.

## Core Value

Generar señales de tendencia accionables y reproducibles a partir de datos reales de mercado, sin depender de procesos manuales ni supuestos no verificados.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Leer y analizar exhaustivamente todos los archivos en la carpeta raíz del proyecto antes de iniciar tareas operativas o de implementación.
- [ ] Construir automáticamente un catálogo maestro de objetos CS2 mediante exploración de la API de CSFloat, con inspección previa de paquetes JSON y volcado de prueba.
- [ ] Implementar extractores concurrentes con AsyncIO para Steam Community Market, Steamdt, Buff163, CS.Money y CSFloat, reutilizando el catálogo maestro.
- [ ] Garantizar tolerancia a fallos en extracción: reintentos, esperas progresivas y persistencia local de respuestas anómalas con marca temporal.
- [ ] Mantener una base de código modular, tipada y auditada automáticamente con Mypy, Ruff, Pytest y Pandera.
- [ ] Completar secuencialmente Fase 0 y Fase 1 como alcance de v1, con aprobación explícita del usuario para avanzar entre fases.

### Out of Scope

- Preprocesamiento avanzado de ventanas temporales y enriquecimiento contextual (Fase 2) — diferido a la siguiente iteración tras estabilizar la capa de extracción.
- Etiquetado automático de muestras futuras (Fase 3) — fuera del alcance de v1 para concentrar validación en adquisición y calidad de datos.
- Entrenamiento baseline con XGBoost (Fase 4) — se aborda después de validar pipeline de datos de fases 0-1.
- Inferencia con modelos fundacionales y ajuste fino (Fases 5 y 6) — pospuesto hasta disponer de dataset consolidado y etiquetado.

## Context

El proyecto está orientado al mercado de Counter-Strike 2 y consume datos de Steam Community Market, Steamdt, Buff163, CS.Money y CSFloat. La estrategia exige exploración previa de interfaces reales (red/API/JS) antes de codificar extractores definitivos, con comportamiento reactivo ante incertidumbre o bloqueos. En la raíz del proyecto se detectan actualmente `claude.md` y `orquestador.md` como fuentes activas de directrices operativas.

## Constraints

- **Execution Environment**: Espacio de usuario estándar, sin permisos de administrador — toda solución debe operar sin elevación de privilegios.
- **Phase Gating**: Progreso secuencial con aprobación explícita para avanzar de fase — evita deriva de alcance.
- **Data Understanding**: Inspección obligatoria de respuestas reales antes de implementar parseo final — prohíbe supuestos sobre estructura de datos.
- **Failure Handling**: Reintentos con backoff y guardado de volcados anómalos — facilita diagnóstico reproducible.
- **Code Quality**: Modularidad estricta, type hints obligatorios y validación con Mypy/Ruff/Pytest/Pandera — garantiza mantenibilidad y consistencia.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Limitar v1 a Fase 0 + Fase 1 | Reducir riesgo inicial y validar primero la adquisición robusta de datos | — Pending |
| Usar CSFloat como fuente inicial para catálogo maestro | Proporciona estructura de objetos para repartir trabajo a extractores secundarios | — Pending |
| Exigir análisis del directorio raíz antes de ejecución | Alinear implementación con restricciones y contexto real del proyecto | ✓ Good |
| Aplicar arquitectura multi-subagente para extracción y revisión | Separar responsabilidades y reforzar calidad de código desde el inicio | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):

1. Requirements invalidated? → Move to Out of Scope with reason
1. Requirements validated? → Move to Validated with phase reference
1. New requirements emerged? → Add to Active
1. Decisions to log? → Add to Key Decisions
1. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):

1. Full review of all sections
1. Core Value check — still the right priority?
1. Audit Out of Scope — reasons still valid?
1. Update Context with current state

______________________________________________________________________

*Last updated: 2026-03-25 after initialization*

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
