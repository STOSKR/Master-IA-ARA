# Contexto del proyecto
Estamos desarrollando un sistema de reconocimiento de tendencias de precios para el mercado de Counter-Strike 2. El flujo de trabajo consta de: obtención de datos de series temporales tabulares, preprocesamiento e integración de variables de contexto, etiquetado automático y entrenamiento de modelos predictivos de clasificación.

# Objetivos y fuentes de datos
El objetivo principal es predecir si el precio de un objeto sube, baja o se mantiene en una ventana temporal futura.
Las fuentes de datos e interfaces que debes utilizar para la extracción son las siguientes:
- Mercado de la comunidad de Steam
- (Añade aquí otras plataformas, mercados de terceros o páginas de estadísticas que vayas a raspar)

# Fases del desarrollo
Por favor, implementa este proyecto fase por fase. No pases a la siguiente sin mi aprobación explícita:
- Fase 1: desarrollo de secuencias de comandos concurrentes (usando AsyncIO) para conectarse a las interfaces del mercado y descargar el historial de precios en formato tabular, aplicando una limpieza inicial de valores anómalos.
- Fase 2: creación del módulo de preprocesamiento que estructura las ventanas temporales e integra la información de contexto específica de cada objeto digital.
- Fase 3: implementación del algoritmo de etiquetado que evalúa los datos futuros respecto a cada ventana temporal y clasifica la muestra en su categoría correspondiente (alcista, bajista o neutral).
- Fase 4: entrenamiento y evaluación inicial de algoritmos clásicos como XGBoost para establecer una línea base de rendimiento.
- Fase 5: configuración de las pruebas de inferencia directa con modelos fundacionales preentrenados de series temporales.
- Fase 6: programación de la etapa de ajuste fino de los modelos fundacionales con los datos específicos del videojuego y generación del análisis comparativo.

# Reglas estrictas de código
1. Modularidad: el código debe estar separado por responsabilidades lógicas utilizando directorios específicos (como src/data, src/models, src/training). No se permiten secuencias de comandos monolíticas.
2. Estilo y tipado: sigue el estándar PEP 8. Es obligatorio el uso de indicaciones de tipo en todas las funciones y métodos. Escribe cadenas de documentación estandarizadas para las funciones complejas.
3. Manejo de errores: incluye siempre lógica de reintentos y esperas progresivas en las llamadas a servicios externos para no exceder los límites de peticiones. Usa bloques de captura de excepciones granulares y el módulo logging en lugar de imprimir por consola.
4. Reproducibilidad: todo el flujo debe ser reproducible. Crea un archivo de configuración para centralizar los hiperparámetros. Establece semillas globales al inicio de los procesos de entrenamiento y evaluación.

# Herramientas de validación
- Utiliza Mypy para la comprobación del tipado estático.
- Utiliza Ruff para el formateo y análisis estático del código.
- Utiliza Pytest para crear pruebas automatizadas de la lógica de partición y etiquetado temporal.
- Utiliza Pandera para validar los esquemas de los datos tabulares durante la extracción (asegurando precios positivos y fechas coherentes).