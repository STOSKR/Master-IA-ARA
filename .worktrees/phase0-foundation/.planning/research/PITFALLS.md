# Domain Pitfalls — CS2 Trend System

**Domain:** Extracción y modelado de tendencias de precios CS2 multi-mercado  
**Researched:** 2026-03-25

## Critical Pitfalls

| Pitfall específico | Qué sale mal en proyectos similares | Señales tempranas (early warning) | Prevención accionable | Fase de mitigación sugerida |
|---|---|---|---|---|
| **Falso “éxito” por anti-bot (HTML 200 en vez de JSON)** | El extractor interpreta una respuesta bloqueada como válida y persiste basura silenciosa. | Caída brusca de filas útiles con `status=200`; payload contiene `<html>`, `captcha`, `verify`. | Validar `content-type`, presencia de claves mínimas y ratio de campos nulos antes de persistir; enviar respuestas inválidas a `dumps/` con timestamp. | **Fase 1** (ingesta robusta) |
| **Dependencia frágil de endpoints internos no versionados** | Steam/CS.Money/Buff cambian rutas o parámetros y el scraper sigue “funcionando” sin datos correctos. | Aumento de respuestas vacías, cambios de shape, `null` masivos tras deploy del proveedor. | Registrar contrato por fuente (campos obligatorios + tipos + cardinalidad) y activar fail-fast con alerta cuando se rompe el contrato. | **Fase 1** (contratos) + **Fase 2** (validación de esquemas) |
| **Sesión/cookies caducadas en Buff163** | El pipeline usa cookie vieja, entra en bucle de reintentos y acelera bloqueo. | Patrón repetido `403/412`, redirección a login, misma longitud de payload en fallos consecutivos. | Gestión explícita de sesión (TTL, rotación manual controlada, detector de expiración), circuit breaker por fuente y pausa de scraping al detectar auth-fail. | **Fase 1** |
| **Concurrencia agresiva que dispara rate limiting** | AsyncIO sin budget por dominio produce baneo IP/cuenta y ventanas incompletas. | Latencia creciente + salto de `429/503`; éxito por request cae al subir workers. | Presupuesto dinámico por fuente (`semaphore` + token bucket), backoff exponencial con jitter y “cooldown” automático por host. | **Fase 1** |
| **Identidad de item inconsistente entre mercados** | Se mezclan series de activos distintos por usar nombres ambiguos (`market_hash_name`, slug, wear, stattrak, souvenir). | Duplicados “imposibles”, splits de una misma skin en múltiples IDs internos, joins con alta tasa de no-match. | Definir `canonical_item_id` con reglas de normalización (arma, skin, wear, stattrak/souvenir, phase) y tabla de mapeo por fuente versionada. | **Fase 0** (catálogo maestro) + **Fase 2** (join) |
| **Desalineación temporal (timezone, granularidad, huecos)** | Series de fuentes distintas se comparan en timestamps no equivalentes; etiquetas se vuelven ruidosas. | Drift de horas al cruzar fuentes, picos en cambios de DST, secuencias con huecos periódicos. | Normalizar a UTC, fijar granularidad canónica, re-muestreo explícito y bandera de imputación por punto. | **Fase 2** |
| **Métrica de precio no homogénea (gross/net, moneda, comisiones)** | Se entrena con “precios” no comparables: comprador vs vendedor, impuestos incluidos/excluidos, FX no sincronizado. | Diferencias sistemáticas por fuente que no se explican por mercado; saltos al cambiar divisa. | Definir `price_basis` único (ej. net seller en USD), pipeline de conversión FX con timestamp y columna de trazabilidad de conversión. | **Fase 1** (ingesta) + **Fase 2** (normalización) |
| **Limpieza de outliers borra eventos reales** | Reglas rígidas eliminan spikes legítimos (operaciones grandes, updates, torneos), sesgando señales. | Caída de varianza tras limpieza; eventos conocidos desaparecen de todas las series. | Separar outlier técnico vs outlier de mercado: winsorización condicionada + etiqueta `is_event_spike` en vez de borrar ciegamente. | **Fase 1** (limpieza inicial) + **Fase 2** (features de contexto) |
| **Schema drift silencioso (campo renombrado/nullable)** | Cambios menores en JSON rompen parseo parcial sin excepción y degradan calidad de dataset. | Columnas nuevas/vacías, incrementos súbitos de nulls, mismatch en Pandera. | Versionar esquemas por fuente, pruebas de contrato diarias y bloqueo de pipeline cuando falla validación crítica. | **Fase 1** + **Fase 2** |
| **Leakage en etiquetado por ventanas mal separadas** | Features incluyen información futura por error de corte temporal y métricas infladas irreales. | Accuracy anormalmente alta en validación, caída fuerte en backtest temporal real. | Enforce estricto de cortes `t0`/horizonte, split temporal forward-only y test de leakage automatizado por muestra. | **Fase 3** |

## Phase-Specific Warnings (prioridad operativa)

| Fase | Riesgo dominante | Mitigación mínima antes de avanzar |
|---|---|---|
| **Fase 0** (catálogo) | IDs canónicos débiles | Congelar `canonical_item_id` y validar cobertura por fuente |
| **Fase 1** (extractores) | Anti-bot + drift + rate-limit | Contratos por endpoint, backoff/jitter, dumps anómalos obligatorios |
| **Fase 2** (preproceso) | Desalineación temporal y de precio | UTC + `price_basis` único + validación Pandera multi-fuente |
| **Fase 3** (etiquetado) | Leakage temporal | Tests automáticos de separación ventana-futuro |

## Signals Dashboard (mínimo recomendado)

- `% respuestas no JSON por fuente` (umbral de alerta por encima de baseline semanal).
- `% filas válidas tras parsing` y `% null por campo crítico`.
- `ratio 429/403/5xx` por host y por minuto.
- `tasa de match` hacia `canonical_item_id` en joins multi-fuente.
- `desviación horaria` entre fuentes para un mismo item y ventana.

## Sources

- `c:\Master-IA-ARA\.planning\PROJECT.md`
- `c:\Master-IA-ARA\claude.md`
- `c:\Master-IA-ARA\orquestador.md`
