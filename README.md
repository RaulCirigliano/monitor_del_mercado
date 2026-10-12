# 🦅 Monitor del Mercado
**Cazador Autónomo de Oportunidades Asimétricas (Filosofía Contrarian)**

Sistema inteligente y autónomo de investigación financiera en Python. Su misión es escanear noticias financieras, titulares RSS, cotizaciones y eventos macroeconómicos para filtrar el **95% del ruido mediático** y generar **Fichas de Oportunidad de Inversión** de alta asimetría matemática ($R/B \ge 1:3$).

> **100% Independiente**: Este sistema no opera órdenes en brokers ni se vincula con plataformas de trading activo; es una central de inteligencia pura.

---

## 🏛️ Filosofía de Evaluación (Las Tres Verdades Contraintuitivas)

1. **Psicología de Masas (Opinión Contraria & Ondas de Elliott)**:
   - Prohibido comprar por euforia o titulares optimistas en techos (identificación de *Trampas de Mercado*).
   - Búsqueda activa de capitulaciones y pánico mediático extremo donde la multitud huye de activos reales.
2. **Sesgo Estructural y Soporte Secular**:
   - Distingue con precisión entre caídas coyunturales (noticias transitorias o pánicos temporales) y quiebras estructurales reales.
3. **Asimetría Matemática (Ratio Riesgo / Beneficio)**:
   - Toda oportunidad propuesta debe tener un ratio mínimo proyectado de **1 a 3** (arriesgar 1 para ganar al menos 3). Si el activo no ofrece esta asimetría, se descarta como ruido.

---

## 🏗️ Arquitectura Híbrida

* **Capa 1 (Python Puro)**: Ingesta rápida y de bajo consumo mediante RSS (`feedparser`), sanitización de HTML (`BeautifulSoup`), y cotizaciones/métricas técnicas con `yfinance` (RSI, distancias a máximos/mínimos de 52 semanas).
* **Capa 2 (IA Local)**: Motor primario con **Ollama** (`qwen2.5:3b`) local, con salida JSON estructurada y validación con **Pydantic**. Motor secundario opcional con **Google Gemini 2.0 Flash**.
* **Capa 3 (Reportes Ejecutivos)**: Generación de fichas ejecutivas en Markdown (`reportes/YYYY-MM-DD_oportunidades.md`) y consola enriquecida con `Rich`.

---

## 🚀 Instalación y Uso

### 1. Activar el entorno virtual
```bash
source .venv/bin/activate
```

### 2. Comprobar el entorno y servicios
```bash
python main.py --check-env
```

### 3. Ejecutar un escaneo completo de mercado
```bash
python main.py --scan
```

### 4. Filtrar por categoría temática
```bash
# Solo criptoactivos
python main.py --category crypto_and_alternatives

# Solo materias primas y energía
python main.py --category commodities_and_energy

# Solo macroeconomía y mercados globales
python main.py --category macro_and_markets
```

### 5. Consultar métricas técnicas de un activo
```bash
python main.py --ticker CL=F
python main.py --ticker BTC-USD
python main.py --ticker TLT
```

### 6. Iniciar el Dashboard Web Interactivo (HTML / JS / CSS)
```bash
python main.py --dashboard
# O especificar puerto:
python main.py --web --port 8520
```
Abre en tu navegador `http://localhost:8520` para interactuar en tiempo real con el sistema, lanzar escaneos por categoría, analizar tickers al instante y explorar las fichas y conclusiones del motor.

---

## 📂 Salida de Reportes
Los reportes se guardan automáticamente en:
`reportes/YYYY-MM-DD_oportunidades_HHMMSS.md`
Cada reporte incluye la tabla de métricas (porcentaje de ruido descartado) y las Fichas Estructuradas con Tesis Contrarian, Catalizador, Nivel de Entrada, Stop Loss y R/B proyectado.
