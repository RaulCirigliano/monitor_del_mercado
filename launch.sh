#!/usr/bin/env bash

# Directorio del proyecto
PROJECT_DIR="/home/raul/Escritorio/proyectos/monitor del mercado"
cd "$PROJECT_DIR" || exit 1

echo "======================================================"
echo "🦅 INICIANDO MONITOR DEL MERCADO"
echo "Cazador Autónomo de Oportunidades Asimétricas"
echo "======================================================"

# 1. Verificar si Ollama está en ejecución
echo -n "🔍 Verificando servicio de Ollama... "
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✔ Activo."
else
    echo "⚠ No detectado. Intentando iniciar ollama serve..."
    if command -v ollama > /dev/null 2>&1; then
        ollama serve > /dev/null 2>&1 &
        sleep 2
    else
        echo "✖ Ollama no está instalado o no se encuentra en el PATH."
    fi
fi

# 2. Verificar entorno virtual
if [ -f "$PROJECT_DIR/.venv/bin/python" ]; then
    PYTHON_EXEC="$PROJECT_DIR/.venv/bin/python"
else
    PYTHON_EXEC="python3"
fi

echo "🚀 Iniciando Dashboard Web y Servicios..."

# Abrir el navegador tras 1.5 segundos
(sleep 2 && xdg-open "http://localhost:8520" > /dev/null 2>&1) &

# Ejecutar el servidor dashboard
exec "$PYTHON_EXEC" main.py --dashboard --port 8520
