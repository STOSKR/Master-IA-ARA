# Technology Stack

**Project:** CS2 Price Trend Intelligence  
**Researched:** 2026-03-25  
**Scope:** Stack base para extracción + preparación + baseline ML en entorno **user-space** (sin privilegios de administrador).

## Recommended Stack

### Core Runtime & Environment
| Technology | Version / Range | Purpose | Why (2025-2026) | Confidence |
|------------|------------------|---------|------------------|------------|
| Python | `>=3.12,<3.14` | Runtime principal | Ecosistema de datos/ML estable, tipado moderno, buen soporte de libs clave | MEDIUM |
| uv | `>=0.11,<0.12` | Gestión de entornos, deps y lock | Reemplaza pip/pip-tools/virtualenv en un flujo único, rápido y reproducible, funciona en user-space | HIGH |
| pydantic + pydantic-settings | `>=2.12,<3` / `>=2.13,<3` | Configuración tipada y validación de payloads | Contratos de datos/config centralizados y estrictos para extractores multi-fuente | HIGH |

### Data Acquisition (Async + Resilience)
| Library | Version / Range | Purpose | Why | Tradeoff | Confidence |
|---------|------------------|---------|-----|----------|------------|
| httpx | `>=0.28,<0.29` | Cliente HTTP async principal | API moderna, HTTP/2, ergonomía para servicios JSON | Menos “battle-tested legacy” que aiohttp en algunos casos extremos | MEDIUM |
| aiohttp | `>=3.13,<4` | Fallback para casos de streaming/sesión compleja | Muy maduro en scraping/API async | Duplicar cliente aumenta complejidad; usar solo cuando httpx no alcance | HIGH |
| tenacity | `>=9.1,<10` | Reintentos con backoff | Encaja con requisito de tolerancia a fallos | Config mala puede amplificar tráfico | HIGH |
| playwright | `>=1.58,<2` | Descubrir/interceptar calls en webs dinámicas (Buff/CS.Money) | Necesario cuando HTML no contiene datos reales y hay app dinámica | Coste operativo mayor (descarga de browsers y tiempos) | HIGH |

### DataFrame, Schema & Local Storage
| Technology | Version / Range | Purpose | Why | Tradeoff | Confidence |
|------------|------------------|---------|-----|----------|------------|
| pandas | `>=3.0,<3.1` | DataFrame principal de pipeline | Máxima compatibilidad con validación, testing y ecosistema ML clásico | Menos rendimiento bruto que Polars en ciertos workloads | MEDIUM |
| pyarrow | `>=23,<24` | Parquet/Arrow I/O | Intercambio columnar eficiente para series temporales | Añade dependencia nativa | HIGH |
| duckdb | `>=1.5,<1.6` | Almacén analítico local embebido | SQL analítico sin servidor (ideal sin admin), consulta directa sobre Parquet | No sustituye un DWH distribuido | HIGH |
| pandera | `>=0.30,<0.31` | Validación de esquemas tabulares | Requisito explícito del proyecto, integración directa con pandas y checks | Curva de diseño de esquemas | HIGH |

### Modeling & Experimentation (Baseline)
| Library | Version / Range | Purpose | Why | Tradeoff | Confidence |
|---------|------------------|---------|-----|----------|------------|
| scikit-learn | `>=1.8,<1.9` | Split, métricas, utilidades de baseline | Estándar para clasificación tabular y evaluación reproducible | No cubre boosting avanzado al nivel de XGBoost | HIGH |
| xgboost | `>=3.2,<3.3` | Modelo baseline principal (Fase 4) | Fuerte baseline en tabular time-window features | Tuning sensible; riesgo de overfitting | HIGH |
| optuna | `>=4.8,<4.9` | Búsqueda de hiperparámetros | Optimización eficiente y simple de integrar | Puede elevar coste computacional rápido | MEDIUM |
| mlflow | `>=3.10,<3.11` | Tracking local de experimentos | Trazabilidad de runs/params/metrics sin infraestructura compleja | Añade capa operativa adicional | MEDIUM |

### Quality & Developer Tooling
| Tool | Version / Range | Purpose | Why | Confidence |
|------|------------------|---------|-----|------------|
| ruff | `>=0.15,<0.16` | Lint + format | Rápido, reemplaza combos más pesados, requisito de proyecto | HIGH |
| mypy | `>=1.19,<1.20` | Tipado estático | Requisito explícito y útil para extractores modulares | HIGH |
| pytest | `>=9.0,<10` | Pruebas automáticas | Estándar de facto para pipelines Python | HIGH |

## Opinionated Defaults (MVP de este proyecto)
- **Lenguaje/plataforma:** Python + `uv`.
- **Extracción:** `httpx` como cliente por defecto + `tenacity`; escalar a `playwright` solo cuando la fuente lo exija.
- **Datos:** `pandas` + `pandera` + Parquet (`pyarrow`), y `duckdb` como capa analítica local.
- **ML baseline:** `xgboost` + `scikit-learn` + `mlflow` (tracking local).

## Alternatives Considered
| Category | Recommended | Alternative | Why Not (for this project now) |
|----------|-------------|-------------|---------------------------------|
| Env manager | uv | Poetry/Pipenv | Más fricción y menor velocidad de resolución en flujos iterativos de scraping/ML |
| Async HTTP | httpx (+aiohttp fallback) | requests + threads | Menos control de concurrencia async y peor alineación con requisito AsyncIO |
| Browser automation | Playwright | Selenium | Setup más pesado y DX inferior para interceptar red moderna en apps JS |
| Storage | DuckDB + Parquet | PostgreSQL local | Requiere servicio persistente; menos ideal en entorno sin admin |
| Pipeline orchestration | CLI/cron user-space + scripts modulares | Airflow autohosteado | Sobreingeniería para v1, mayor carga operativa |

## What NOT to Use (v1)
| Avoid | Why |
|------|-----|
| Scraping HTML-only (BeautifulSoup como estrategia principal) | Steam/Buff/CS.Money son dinámicos; los datos útiles suelen venir por JSON/API interna |
| Notebook-driven monolith | Rompe modularidad, auditabilidad de tipos y testing requerido |
| Multiproceso agresivo para I/O de red | AsyncIO es más simple/controlable para este caso de extracción concurrente |
| Introducir Spark/Dask desde inicio | Complejidad innecesaria antes de validar extracción, limpieza y etiquetado |

## Installation (user-space first)
```bash
# 1) Tooling local (sin admin) y Python del proyecto
uv python install 3.12
uv venv --python 3.12

# 2) Dependencias base
uv add httpx aiohttp tenacity playwright pydantic pydantic-settings \
  pandas pyarrow duckdb pandera scikit-learn xgboost optuna mlflow \
  typer python-dotenv orjson

# 3) Calidad
uv add --dev ruff mypy pytest

# 4) Navegadores Playwright (en user-space)
uv run playwright install
```

## Confidence Notes
| Area | Level | Why |
|------|-------|-----|
| Packaging/tooling (`uv`) | HIGH | Evidencia en docs oficiales + versión actual verificada |
| Data validation (`pydantic`, `pandera`) | HIGH | Docs oficiales claras + encaje directo con requisitos del proyecto |
| Async extraction (`httpx`/`aiohttp`/`playwright`) | MEDIUM-HIGH | Librerías maduras; elección exacta por fuente depende de inspección real de red |
| Local analytics (`duckdb` + parquet) | HIGH | Patrón estándar para analytics local sin servicios admin |
| “Standard 2025-2026” claim global | MEDIUM | Basado en estado actual de ecosistema + verificación parcial vía fuentes oficiales/PyPI |

## Sources
- https://docs.astral.sh/uv/
- https://pypi.org/pypi/uv/json
- https://playwright.dev/python/docs/intro
- https://pypi.org/pypi/playwright/json
- https://docs.pydantic.dev/latest/
- https://pypi.org/pypi/pydantic/json
- https://pandera.readthedocs.io/en/stable/
- https://pypi.org/pypi/pandera/json
- https://duckdb.org/docs/stable/
- https://pypi.org/pypi/duckdb/json
- https://pypi.org/pypi/pandas/json
- https://pypi.org/pypi/pyarrow/json
- https://pypi.org/pypi/httpx/json
- https://pypi.org/pypi/aiohttp/json
- https://pypi.org/pypi/tenacity/json
- https://pypi.org/pypi/scikit-learn/json
- https://pypi.org/pypi/xgboost/json
- https://pypi.org/pypi/optuna/json
- https://pypi.org/pypi/mlflow/json
- https://pypi.org/pypi/ruff/json
- https://pypi.org/pypi/mypy/json
- https://pypi.org/pypi/pytest/json
