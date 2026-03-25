# Requirements: CS2 Price Trend Intelligence

**Defined:** 2026-03-25
**Core Value:** Generar señales de tendencia accionables y reproducibles a partir de datos reales de mercado, sin depender de procesos manuales ni supuestos no verificados.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Project Context

- [ ] **CTX-01**: El sistema debe leer y analizar todos los archivos presentes en la raíz del proyecto antes de iniciar tareas de extracción o implementación.
- [ ] **CTX-02**: El sistema debe operar íntegramente en espacio de usuario estándar, sin requerir permisos de administrador.
- [ ] **CTX-03**: El sistema debe bloquear el avance de fase hasta recibir aprobación explícita del usuario.

### Catalog Foundation

- [ ] **CAT-01**: El sistema debe extraer automáticamente desde CSFloat la lista de armas, skins, desgaste y atributos especiales para construir el catálogo maestro.
- [ ] **CAT-02**: El sistema debe ejecutar una inspección previa de paquetes de red y generar un volcado de prueba JSON antes de promover el extractor definitivo del catálogo.
- [ ] **CAT-03**: El sistema debe persistir un `canonical_item_id` estable para permitir mapeo consistente entre todas las fuentes de mercado.

### Multi-Source Extraction

- [ ] **EXT-01**: El sistema debe implementar extracción concurrente con AsyncIO para Steam Community Market.
- [ ] **EXT-02**: El sistema debe implementar extracción concurrente con AsyncIO para Steamdt.
- [ ] **EXT-03**: El sistema debe implementar extracción concurrente con AsyncIO para Buff163.
- [ ] **EXT-04**: El sistema debe implementar extracción concurrente con AsyncIO para CS.Money.
- [ ] **EXT-05**: El sistema debe implementar extracción concurrente con AsyncIO para CSFloat.
- [ ] **EXT-06**: El sistema debe ejecutar una fase de inspección de respuesta (JSON/HTML/red) en cada fuente antes de habilitar su parser final.

### Reliability and Quality

- [ ] **REL-01**: El sistema debe aplicar reintentos con espera progresiva ante fallos de red o servidor en todas las fuentes.
- [ ] **REL-02**: El sistema debe guardar el cuerpo bruto de respuestas anómalas en un directorio local de volcados con marca temporal.
- [ ] **REL-03**: El sistema debe exponer observabilidad mínima por ejecución (`run_id`, recuentos por fuente, recuentos de fallo).
- [ ] **QLT-01**: El sistema debe producir un contrato tabular histórico unificado con campos obligatorios (`timestamp_utc`, `source`, `canonical_item_id`, `price`, `currency`, `price_basis`) y campos opcionales (`volume`, `availability`).
- [ ] **QLT-02**: El sistema debe validar esquemas tabulares con Pandera antes de publicar datos curados.
- [ ] **QLT-03**: El sistema debe detectar duplicados y aplicar saneamiento básico de valores atípicos en el flujo de extracción v1.

### Code Governance

- [ ] **QAG-01**: El código debe estar estructurado de forma modular por responsabilidades; se prohíben scripts monolíticos.
- [ ] **QAG-02**: Todas las funciones y métodos deben incluir indicaciones de tipo.
- [ ] **QAG-03**: El pipeline de validación debe incluir Mypy y Ruff para control estático en cada extractor.
- [ ] **QAG-04**: El proyecto debe incluir pruebas automatizadas con Pytest para los componentes críticos de fase 0-1.

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Data Preparation

- **DPR-01**: Construir ventanas temporales y enriquecer contexto específico por objeto (fase 2).
- **DPR-02**: Formalizar políticas de armonización temporal y normalización avanzada entre mercados.

### Labeling and Modeling

- **MLB-01**: Implementar etiquetado automático alcista/bajista/neutral con ventanas futuras y controles anti-leakage (fase 3).
- **MLB-02**: Entrenar y evaluar baseline clásico con XGBoost y métricas reproducibles (fase 4).
- **MLB-03**: Ejecutar inferencia con modelos fundacionales preentrenados de series temporales (fase 5).
- **MLB-04**: Ajustar finamente modelos fundacionales con datos del dominio CS2 y comparar resultados (fase 6).

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Automatización de señales/ejecución en tiempo real | Riesgo operativo alto y fuera del objetivo de v1 (base de datos confiable). |
| Desarrollo de dashboard/UI completo en v1 | No es crítico para validar robustez de catálogo y extracción. |
| Bypass agresivo de protecciones anti-bot | Fragilidad elevada; se prioriza comportamiento reactivo y trazabilidad de fallos. |
| Entrenamiento de modelos en paralelo a fase 0-1 | Aumenta complejidad antes de estabilizar contratos de datos. |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CTX-01 | Phase 0 | Pending |
| CTX-02 | Phase 0 | Pending |
| CTX-03 | Phase 0 | Pending |
| CAT-01 | Phase 0 | Pending |
| CAT-02 | Phase 0 | Pending |
| CAT-03 | Phase 0 | Pending |
| EXT-01 | Phase 1 | Pending |
| EXT-02 | Phase 1 | Pending |
| EXT-03 | Phase 1 | Pending |
| EXT-04 | Phase 1 | Pending |
| EXT-05 | Phase 1 | Pending |
| EXT-06 | Phase 1 | Pending |
| REL-01 | Phase 1 | Pending |
| REL-02 | Phase 1 | Pending |
| REL-03 | Phase 1 | Pending |
| QLT-01 | Phase 1 | Pending |
| QLT-02 | Phase 1 | Pending |
| QLT-03 | Phase 1 | Pending |
| QAG-01 | Phase 0 | Pending |
| QAG-02 | Phase 0 | Pending |
| QAG-03 | Phase 1 | Pending |
| QAG-04 | Phase 1 | Pending |

**Coverage:**
- v1 requirements: 22 total
- Mapped to phases: 22
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-25*
*Last updated: 2026-03-25 after initial definition*
