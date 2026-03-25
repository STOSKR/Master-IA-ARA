# Roadmap: CS2 Price Trend Intelligence

## Scope Guardrail

v1 se limita estrictamente a **Phase 0 + Phase 1** según `PROJECT.md`. Cualquier trabajo de fases 2+ queda fuera de este roadmap.

## Phases

- [ ] **Phase 0: Foundation & Canonical Catalog** - Asegurar contexto operativo, catálogo maestro CS2 y base de gobernanza técnica para extracción.
- [ ] **Phase 1: Multi-Source Extraction & Data Quality** - Entregar extracción concurrente robusta y contrato tabular histórico unificado validado.

## Phase Details

### Phase 0: Foundation & Canonical Catalog
**Goal**: El usuario cuenta con una base de trabajo validada (contexto, restricciones operativas y catálogo canónico) que habilita extracción multifuente sin ambigüedad de identidad.
**Depends on**: Nothing (first phase)
**Requirements**: CTX-01, CTX-02, CTX-03, CAT-01, CAT-02, CAT-03, QAG-01, QAG-02
**Success Criteria** (what must be TRUE):
  1. El análisis de contexto de la raíz del proyecto está completado y puede auditarse antes de iniciar extractores.
  2. Existe un catálogo maestro de CS2 construido desde CSFloat con `canonical_item_id` persistido y utilizable por fuentes externas.
  3. Se conserva evidencia de inspección previa (volcado JSON de prueba) anterior a cualquier promoción del extractor definitivo de catálogo.
  4. La base de código de fase está organizada por módulos de responsabilidad y las funciones/métodos de la fase usan tipado explícito.
  5. El usuario emite aprobación explícita de cierre de Phase 0 para habilitar el inicio de Phase 1.
**Plans**: TBD

### Phase 1: Multi-Source Extraction & Data Quality
**Goal**: El usuario obtiene series históricas confiables desde cinco mercados con tolerancia a fallos, observabilidad mínima y validación de calidad tabular.
**Depends on**: Phase 0
**Requirements**: EXT-01, EXT-02, EXT-03, EXT-04, EXT-05, EXT-06, REL-01, REL-02, REL-03, QLT-01, QLT-02, QLT-03, QAG-03, QAG-04
**Success Criteria** (what must be TRUE):
  1. Las cinco fuentes (Steam Community Market, Steamdt, Buff163, CS.Money y CSFloat) se ejecutan con extracción concurrente AsyncIO usando el catálogo canónico.
  2. Cada fuente conserva evidencia de inspección previa de respuesta (JSON/HTML/red) antes de activar su parser final.
  3. Los fallos transitorios aplican reintentos con espera progresiva y las respuestas anómalas se guardan en volcados locales con marca temporal.
  4. Cada ejecución produce observabilidad mínima (`run_id`, recuentos por fuente y recuentos de fallo) verificable por el usuario.
  5. Los datos históricos se publican bajo contrato tabular unificado y validación Pandera, con control de duplicados y saneamiento básico de atípicos.
**Plans**: TBD

## Requirement Coverage Map (v1)

- **Phase 0 (8):** CTX-01, CTX-02, CTX-03, CAT-01, CAT-02, CAT-03, QAG-01, QAG-02
- **Phase 1 (14):** EXT-01, EXT-02, EXT-03, EXT-04, EXT-05, EXT-06, REL-01, REL-02, REL-03, QLT-01, QLT-02, QLT-03, QAG-03, QAG-04

**Coverage check**: 22/22 requisitos v1 mapeados (100%).

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 0. Foundation & Canonical Catalog | 0/0 | Not started | - |
| 1. Multi-Source Extraction & Data Quality | 0/0 | Not started | - |

---
*Last updated: 2026-03-25*

## Maintenance Update 2026-03-25
- [x] Step 1 completed: duplicate/unused code cleanup and refactor in scraper-related modules.
- [x] Step 2 completed: live endpoint validation performed, blocking/auth failures reproduced, and scraper hardening applied.
- [x] Step 2 fix applied: CSFloat authentication support added via CSFLOAT_API_KEY or CSFLOAT_COOKIE in Phase 0/Phase 1 paths.
- [ ] Live extraction success against protected CSFloat endpoint remains pending until valid authentication credentials are configured.

## Next Development Steps
1. Configure CSFLOAT_API_KEY or CSFLOAT_COOKIE in runtime environment.
2. Re-run phase0 probe and phase1 extraction using authenticated session.
3. Validate persisted raw/curated outputs and metrics artifacts in data directories.
4. Continue with Phase 2 windowing implementation once authenticated extraction is stable.
