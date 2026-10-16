# 🦅 Monitor del Mercado
**Cazador Autónomo de Oportunidades Asimétricas (Filosofía Contrarian)**

Sistema inteligente y autónomo de investigación financiera en Python. Su misión es escanear noticias financieras, titulares RSS, cotizaciones y eventos macroeconómicos para filtrar el **95% del ruido mediático** y generar **Fichas de Oportunidad de Inversión** de alta asimetría matemática ($R/B \ge 1:3$).

> **No ejecuta órdenes**: El monitor no opera en brokers. El dashboard puede reenviar una directiva al endpoint local de Trading Ollama, pero requiere confirmación manual salvo que se active explícitamente la auto-inyección.

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

* **Capa 1 (Python Puro)**: Ingesta rápida y de bajo consumo mediante RSS (`feedparser`), sanitización de HTML (`BeautifulSoup`), y cotizaciones/métricas técnicas con `yfinance` (RSI de Wilder, distancias a máximos/mínimos de 52 semanas).
* **Capa 2 (IA Local)**: Motor primario con **Ollama** (`qwen2.5:3b`) local, con salida JSON estructurada y validación con **Pydantic**. Motor secundario opcional con **Google Gemini 2.0 Flash**.
* **Capa 3 (Reportes Ejecutivos)**: Generación de fichas ejecutivas en Markdown (`reportes/YYYY-MM-DD_oportunidades.md`) y consola enriquecida con `Rich`.

---

## 🚀 Instalación y Uso

### Instalar dependencias
```bash
python -m venv .venv
# Linux / macOS
source .venv/bin/activate
# Windows (PowerShell): .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Google Gemini es opcional. Para usar `--gemini`, instala además:
```bash
python -m pip install -r requirements-gemini.txt
```

### 1. Activar el entorno virtual
```bash
source .venv/bin/activate
```

En Windows, también puedes iniciar el dashboard con `lanzar-bot.bat`; en Linux, usa `./launch.sh`.

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
El dashboard escucha solo en `127.0.0.1`; no está pensado para acceso desde otros equipos. La auto-inyección al servicio local de Trading Ollama es opcional y está desactivada por defecto; activarla transmite una tesis al servicio externo, pero el monitor no ejecuta operaciones ni se conecta a brokers.
Con Trading Ollama en ejecución, el selector de cerebro carga los modelos instalados en Ollama y sincroniza la selección central entre ambas interfaces. El lanzador integrado `lanzar_todo.py` está en la raíz del proyecto Trading Ollama; puede usarse desde allí para iniciar y supervisar ambos sistemas.

---

## 📂 Salida de Reportes
Los reportes se guardan automáticamente en:
`reportes/YYYY-MM-DD/RADAR_YYYY-MM-DD_HHMMSSffffff.md` o `ESPECIFICO_<directiva>_YYYY-MM-DD_HHMMSSffffff.md`
Cada reporte incluye la tabla de métricas (porcentaje de ruido descartado) y las Fichas Estructuradas con Tesis Contrarian, Catalizador, Nivel de Entrada, Stop Loss y R/B proyectado.
