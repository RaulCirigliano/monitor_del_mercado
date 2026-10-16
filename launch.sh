#!/usr/bin/env bash

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)" || {
    echo "No se pudo localizar el directorio del proyecto." >&2
    exit 1
}
cd "$PROJECT_DIR" || {
    echo "No se pudo acceder al directorio del proyecto: $PROJECT_DIR" >&2
    exit 1
}

echo "======================================================"
echo "🦅 INICIANDO MONITOR DEL MERCADO"
echo "Cazador Autónomo de Oportunidades Asimétricas"
echo "======================================================"

# 1. Verificar si Ollama está en ejecución
echo -n "🔍 Verificando servicio de Ollama... "
if command -v curl > /dev/null 2>&1 && curl -fsS --max-time 2 http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✔ Activo."
else
    echo "⚠ No detectado. Intentando iniciar ollama serve..."
    if command -v ollama > /dev/null 2>&1; then
        ollama serve > /dev/null 2>&1 &
        sleep 2
        if command -v curl > /dev/null 2>&1 && curl -fsS --max-time 2 http://localhost:11434/api/tags > /dev/null 2>&1; then
            echo "✔ Ollama iniciado."
        else
            echo "⚠ Ollama no respondió; el dashboard iniciará igualmente, pero el análisis con IA no estará disponible."
        fi
    else
        echo "⚠ Ollama no está instalado o no se encuentra en el PATH; el dashboard iniciará sin IA local."
    fi
fi

# 2. Verificar entorno virtual
if [ -x "$PROJECT_DIR/.venv/bin/python" ]; then
    PYTHON_EXEC="$PROJECT_DIR/.venv/bin/python"
elif command -v python3 > /dev/null 2>&1; then
    PYTHON_EXEC="$(command -v python3)"
elif command -v python > /dev/null 2>&1; then
    PYTHON_EXEC="$(command -v python)"
else
    echo "✖ No se encontró Python. Instala Python 3 y vuelve a ejecutar este lanzador." >&2
    exit 1
fi

if ! "$PYTHON_EXEC" -c 'import bs4, dotenv, feedparser, httpx, pandas, pydantic, rich, yaml, yfinance' > /dev/null 2>&1; then
    echo "✖ Faltan dependencias de Python. Activa el entorno e instala requirements.txt:" >&2
    echo "  $PYTHON_EXEC -m pip install -r \"$PROJECT_DIR/requirements.txt\"" >&2
    exit 1
fi

echo "🚀 Iniciando Dashboard Web y Servicios..."

# Ejecutar el servidor dashboard
exec "$PYTHON_EXEC" main.py --dashboard --port 8520
