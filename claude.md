# Contexto del Proyecto
Estamos desarrollando un sistema de reconocimiento de patrones técnicos en gráficas financieras para el mercado de Counter-Strike 2 (CS2). 
El pipeline consta de: obtención de datos de series temporales, renderizado a imágenes 2D (velas japonesas), etiquetado automático (alcista/bajista/neutral) y entrenamiento de una Red Neuronal Convolucional (PyTorch/TensorFlow) para clasificación predictiva.

# Fases del Desarrollo (Tareas)
Por favor, ayúdame a implementar este proyecto fase por fase. No pases a la siguiente sin que yo apruebe la actual:
- [ ] **Fase 1 (Data Fetching):** Scripts para conectarse a las APIs del mercado y descargar series temporales guardándolas en formato Parquet o CSV (limpiando outliers).
- [ ] **Fase 2 (Generación de Imágenes):** Módulo que convierte el dataframe histórico (OHLCV) en imágenes de velas japonesas 2D, usando librerías como `mplfinance` o `matplotlib` puro sin ejes ni texto.
- [ ] **Fase 3 (Etiquetado Automático):** Algoritmo que lee los datos futuros (N días después de la gráfica generada) y clasifica la imagen en carpetas o metadatos (`bullish`, `bearish`, `neutral`).
- [ ] **Fase 4 (Modelo CNN):** Definición de la arquitectura (ej. ResNet ligera), Dataloaders personalizados y bucle de entrenamiento/validación con métricas (Accuracy, F1-Score).

# Reglas Estrictas de Código (Clean Code)

1. **Modularidad (Arquitectura):**
   - El código debe estar separado por responsabilidades lógicas. Usa carpetas como `src/data`, `src/visualization`, `src/models`, `src/training`.
   - Nada de scripts monolíticos de 1000 líneas.

2. **Estilo y Tipado (Python):**
   - Sigue el estándar PEP 8.
   - **Obligatorio:** Usa Type Hints (`typing`) en TODAS las funciones y métodos (ej. `def process_data(df: pd.DataFrame) -> np.ndarray:`).
   - Escribe docstrings concisos bajo el estándar de Google o NumPy para funciones complejas.

3. **Manejo de Errores y APIs:**
   - Si implementas llamadas a API, incluye siempre lógica de reintentos (`retries`) y esperas progresivas (`exponential backoff`) para no exceder los rate limits.
   - Usa bloques `try-except` granulares, no genéricos. Usa el módulo `logging`, no uses `print()`.

4. **Reproducibilidad:**
   - Todo debe ser reproducible. Crea un archivo `config.yaml` o `settings.py` para centralizar hiperparámetros (tamaño de imagen, batch size, learning rate).
   - Establece "semillas" (seeds) globales al inicio de los scripts de entrenamiento para PyTorch/NumPy/Random.

5. **Gestión de Memoria:**
   - Al renderizar miles de imágenes con Matplotlib, asegúrate de cerrar explícitamente las figuras (`plt.close(fig)`) en cada iteración para evitar fugas de memoria (memory leaks).