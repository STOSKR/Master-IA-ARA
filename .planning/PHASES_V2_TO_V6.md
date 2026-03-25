# Fases Nuevas (v2+) — Plan de Continuidad

## Estado de partida
- Base v1 estabilizada en extracción y calidad de datos.
- Contrato tabular unificado disponible para modelado.
- Objetivo de este documento: definir ejecución secuencial de Phase 2 a Phase 6.

## Phase 2 — Ventanas Temporales y Contexto Enriquecido
### Objetivo
Construir datasets por ventanas temporales consistentes, enriquecidos con variables de contexto por item y por mercado.

### Entregables
- Módulo de windowing reusable con stride y horizon configurables.
- Integración de features de contexto (liquidez, volatilidad, spread entre mercados, estacionalidad temporal).
- Validadores Pandera para dataset de features.

### Criterios de salida
- Generación determinista de ventanas con seed fija.
- Sin leakage temporal en el armado de features.
- Pruebas unitarias para slicing temporal y joins de contexto.

## Phase 3 — Etiquetado Automático de Tendencia
### Objetivo
Clasificar cada muestra en alcista, bajista o neutral usando ventana futura y umbrales configurables.

### Entregables
- Módulo de labeling parametrizable por horizon y delta mínimo.
- Reporte de distribución de clases por fuente y por item.
- Validaciones anti-leakage y consistencia temporal.

### Criterios de salida
- Reproducibilidad completa del etiquetado.
- Cobertura de pruebas para casos límite (mercado plano, gaps, baja liquidez).
- Artefacto versionado de labels para entrenamiento.

## Phase 4 — Baseline Clásico (XGBoost)
### Objetivo
Entrenar y evaluar una línea base robusta para medir capacidad predictiva inicial.

### Entregables
- Pipeline de entrenamiento con split temporal estricto.
- Métricas: macro-F1, balanced accuracy, matriz de confusión y calibración.
- Registro de experimentos y artefactos de modelo.

### Criterios de salida
- Baseline reproducible con configuración versionada.
- Informe comparativo por fuente y por segmentos de liquidez.
- Pruebas de smoke para entrenamiento e inferencia batch.

## Phase 5 — Inferencia con Modelos Fundacionales
### Objetivo
Probar modelos fundacionales preentrenados de series temporales en inferencia directa sobre el dominio CS2.

### Entregables
- Adaptadores de inferencia para uno o más modelos fundacionales.
- Protocolo uniforme de evaluación frente al baseline clásico.
- Reporte de costo/latencia/calidad por modelo.

### Criterios de salida
- Pipeline de inferencia estable para lotes de prueba.
- Métricas comparables contra Phase 4.
- Registro de supuestos y limitaciones por modelo.

## Phase 6 — Ajuste Fino y Comparativa Final
### Objetivo
Ajustar modelos fundacionales con datos del dominio CS2 y consolidar comparación final con baseline.

### Entregables
- Pipeline de fine-tuning con validación temporal y control de sobreajuste.
- Evaluación post-fine-tuning con mismas métricas de Phase 4/5.
- Documento de decisión técnica para modelo final operativo.

### Criterios de salida
- Mejora medible frente a baseline y/o mejor costo-rendimiento.
- Proceso reproducible de fine-tuning con tracking de versión.
- Recomendación final de despliegue en entorno de inferencia.

## Reglas transversales para todas las fases
- Tipado estricto y modularidad por responsabilidad.
- Validación continua con Ruff, Mypy y Pytest.
- Persistencia de artefactos con metadatos de ejecución.
- No avanzar de fase sin validación funcional de la fase previa.
