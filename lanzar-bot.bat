@echo off
setlocal

cd /d "%~dp0"
if errorlevel 1 (
    echo No se pudo acceder al directorio del proyecto.
    exit /b 1
)

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"
    "%PYTHON_EXE%" -c "import bs4, dotenv, feedparser, httpx, pandas, pydantic, rich, yaml, yfinance" >nul 2>&1
    if errorlevel 1 (
        echo Faltan dependencias. Ejecuta:
        echo "%PYTHON_EXE%" -m pip install -r requirements.txt
        exit /b 1
    )
    "%PYTHON_EXE%" main.py --dashboard --port 8520
) else (
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 -c "import bs4, dotenv, feedparser, httpx, pandas, pydantic, rich, yaml, yfinance" >nul 2>&1
        if errorlevel 1 (
            echo Faltan dependencias. Ejecuta:
            echo py -3 -m pip install -r requirements.txt
            exit /b 1
        )
        py -3 main.py --dashboard --port 8520
    ) else (
        where python >nul 2>nul
        if errorlevel 1 (
            echo No se encontro Python. Instala Python 3 y vuelve a ejecutar este lanzador.
            exit /b 1
        )
        python -c "import bs4, dotenv, feedparser, httpx, pandas, pydantic, rich, yaml, yfinance" >nul 2>&1
        if errorlevel 1 (
            echo Faltan dependencias. Ejecuta:
            echo python -m pip install -r requirements.txt
            exit /b 1
        )
        python main.py --dashboard --port 8520
    )
)

if errorlevel 1 (
    echo El dashboard finalizo con un error.
    exit /b 1
)
