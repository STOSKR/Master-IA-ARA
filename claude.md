# Contexto del proyecto
Estamos desarrollando un sistema de reconocimiento de tendencias de precios para el mercado de Counter-Strike 2. El flujo de trabajo consta de: obtención de datos de series temporales tabulares, preprocesamiento e integración de variables de contexto, etiquetado automático y entrenamiento de modelos predictivos de clasificación.

# Objetivos y fuentes de datos
El objetivo principal es predecir si el precio de un objeto sube, baja o se mantiene en una ventana temporal futura.
Las fuentes de datos e interfaces que debes explorar y utilizar para la extracción son:
- Mercado de la comunidad de Steam
- Steamdt
- Buff (Buff163)
- CS.Money
- CSFloat

# Fases del desarrollo
Por favor, implementa este proyecto fase por fase. No pases a la siguiente sin mi aprobación explícita:
- Fase 1: desarrollo de secuencias de comandos concurrentes (usando AsyncIO) para conectarse a las interfaces del mercado y descargar el historial de precios en formato tabular, aplicando una limpieza inicial de valores anómalos.
- Fase 2: creación del módulo de preprocesamiento que estructura las ventanas temporales e integra la información de contexto específica de cada objeto digital.
- Fase 3: implementación del algoritmo de etiquetado que evalúa los datos futuros respecto a cada ventana temporal y clasifica la muestra en su categoría correspondiente (alcista, bajista o neutral).
- Fase 4: entrenamiento y evaluación inicial de algoritmos clásicos como XGBoost para establecer una línea base de rendimiento.
- Fase 5: configuración de las pruebas de inferencia directa con modelos fundacionales preentrenados de series temporales.
- Fase 6: programación de la etapa de ajuste fino de los modelos fundacionales con los datos específicos del videojuego y generación del análisis comparativo.

# Comportamiento reactivo y exploratorio
1. Proactividad ante la duda: si te falta contexto sobre la estructura de los datos, detén la ejecución inmediatamente y hazme preguntas claras. No asumas ni inventes implementaciones.
2. Exploración web previa obligatoria: nunca escribas un script de extracción definitivo sin antes haber descargado y analizado una muestra real de la página o de su interfaz de programación. Utiliza scripts temporales para inspeccionar qué devuelve el servidor antes de programar la solución final.

# Guion de exploración por plataforma
Antes de programar la extracción para cada web, aplica estas pautas específicas de exploración:
- Steam: no dependas solo de analizar el HTML. Inspecciona si los datos del gráfico se cargan mediante variables de JavaScript en el código fuente (como la variable line1) o a través de peticiones internas a un extremo JSON.
- Buff163: esta plataforma tiene fuertes medidas de seguridad. Explora el uso de las interfaces de programación internas que devuelve el navegador al inspeccionar la red y prepárate para gestionar la inyección de cookies de sesión, ya que los datos no son públicos sin autenticación.
- CS.Money: es una aplicación web fuertemente dinámica. No analices el HTML inicial. Utiliza las herramientas de red para interceptar las llamadas a su interfaz de programación que contienen los datos tabulares en formato JSON.
- CSFloat: esta plataforma suele ofrecer una interfaz de programación pública o semi-pública muy estructurada. Busca su documentación o intercepta las llamadas de red para extraer directamente los datos en formato estructurado sin necesidad de raspar el código web.

# Reglas estrictas de código
1. Modularidad: el código debe estar separado por responsabilidades lógicas utilizando directorios específicos. No se permiten secuencias de comandos monolíticas.
2. Estilo y tipado: sigue el estándar oficial de estilo. Es obligatorio el uso de indicaciones de tipo en todas las funciones y métodos. Escribe cadenas de documentación estandarizadas para las funciones complejas.
3. Manejo de errores y depuración: incluye siempre lógica de reintentos y esperas progresivas. Si una petición falla repetidamente, captura el cuerpo de la respuesta en bruto y guárdalo en un directorio local de volcados con una marca de tiempo.
4. Reproducibilidad: crea un archivo de configuración para centralizar los hiperparámetros y establece semillas globales.

# Herramientas de validación
- Utiliza Mypy para la comprobación del tipado estático.
- Utiliza Ruff para el formateo y análisis estático del código.
- Utiliza Pytest para crear pruebas automatizadas.
- Utiliza Pandera para validar los esquemas de los datos tabulares.