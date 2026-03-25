# Execution Plan — Phase 0 + Phase 1

## Objective

Implementar de forma inmediata el alcance v1 definido en `ROADMAP.md` y `REQUIREMENTS.md`:

- **Phase 0**: Foundation & Canonical Catalog.
- **Phase 1**: Multi-Source Extraction & Data Quality.

El trabajo se ejecuta con subagentes independientes en ramas separadas, commits atómicos y ciclos de revisión/corrección hasta alcanzar una base sin errores relevantes.

## Constraint Lock

1. Entorno **sin privilegios de administrador**.
2. Arquitectura **modular** (prohibidos scripts monolíticos).
3. Tipado obligatorio en todas las funciones/métodos.
4. Exploración previa obligatoria por fuente antes de parser definitivo.
5. Manejo de fallos obligatorio: retries + backoff + dumps anómalos con timestamp.
6. Validación con Mypy, Ruff, Pytest y Pandera.

## Work Breakdown

## Wave 1 (Parallel)

### Subagent A — Branch: `feat/phase0-foundation`

**Scope**
- Scaffold del proyecto Python.
- Configuración central (`settings`, semillas, rutas user-space).
- Logging, retries y utilidades de dump.
- Modelos/base schema canónica (`canonical_item_id`).
- CLI base para orquestación de jobs.

**Deliverables**
- Estructura modular `src/`.
- `pyproject.toml`, config de Ruff/Mypy/Pytest.
- Módulos base de dominio y utilidades.

### Subagent B — Branch: `feat/phase0-csfloat-catalog`

**Scope**
- Prober de CSFloat para inspección y volcado de muestra.
- Servicio de catálogo maestro con persistencia local.
- Generación de `canonical_item_id`.

**Deliverables**
- `probe_runner` para CSFloat.
- `catalog_service` con salida tabular.
- Persistencia en `.data/catalog/`.

### Subagent C — Branch: `feat/phase1-extraction-kernel`

**Scope**
- Núcleo de extracción AsyncIO compartido.
- Contrato de conectores por fuente.
- Orquestador concurrente multifuente.
- Observabilidad mínima por ejecución (`run_id`, métricas de recuento y fallos).

**Deliverables**
- Interfaces y pipeline de extracción.
- Política global de retries/backoff.
- Registro de eventos operativos.

## Wave 2 (Parallel, depends on Wave 1)

### Subagent D — Branch: `feat/phase1-connectors-steam-steamdt`

**Scope**
- Conectores y probes para Steam + Steamdt.
- Inspección previa obligatoria y dumps de respuesta.
- Parser hacia contrato tabular unificado.

### Subagent E — Branch: `feat/phase1-connectors-buff-csmoney-csfloat`

**Scope**
- Conectores y probes para Buff163 + CS.Money + CSFloat.
- Gestión explícita de errores de sesión/bloqueo.
- Parser hacia contrato tabular unificado.

### Subagent F — Branch: `feat/phase1-quality-gates`

**Scope**
- Validación Pandera del esquema canónico.
- Detección de duplicados y saneamiento básico de outliers.
- Persistencia `raw`, `dumps`, `curated`.

## Wave 3 (Parallel Review Loops)

Por cada rama de subagente de implementación:

1. Lanzar subagente revisor en la misma rama.
2. Ejecutar auditoría de:
   - Ruff
   - Mypy
   - Pytest
   - consistencia arquitectónica y tipado
3. Si detecta hallazgos: crear corrección en la misma rama y recommit.
4. Repetir bucle hasta resultado limpio o con incidencias no bloqueantes explícitas.

## Integration Strategy

1. Rebase/merge de ramas por orden de dependencia:
   - `feat/phase0-foundation`
   - `feat/phase0-csfloat-catalog`
   - `feat/phase1-extraction-kernel`
   - `feat/phase1-connectors-steam-steamdt`
   - `feat/phase1-connectors-buff-csmoney-csfloat`
   - `feat/phase1-quality-gates`
2. Resolver conflictos manteniendo contratos de interfaz compartidos.
3. Ejecutar validación final del workspace completo.

## Verification Criteria (Done Definition)

### Phase 0 done
- Lectura/contexto de raíz trazable en artefactos.
- Catálogo maestro CSFloat con `canonical_item_id` persistido.
- Evidencia de probe JSON previa a parser definitivo.
- Base modular tipada.

### Phase 1 done
- Async extraction de 5 fuentes implementada vía núcleo común.
- Probe por fuente + dumps anómalos timestamped.
- Retries/backoff activos por defecto.
- Contrato tabular unificado y validado con Pandera.
- Checks de calidad: duplicados + outliers básicos.
- Pipeline de calidad (ruff/mypy/pytest) ejecutable.

## Risk Controls

- Si una fuente no ofrece endpoint estable o requiere autenticación compleja: se preserva modo reactivo (stop + dump + error explícito), nunca parseo por suposición.
- Si un validador falla, no se publica en `curated`.
- Si un revisor detecta violación de modularidad o tipado, la rama no se integra hasta corregir.
