#!/usr/bin/env python3
"""
Monitor del Mercado — Cazador Autónomo de Oportunidades Asimétricas.
Punto de entrada de línea de comandos (CLI).
"""

import argparse
import sys
from rich.console import Console

from config import settings
from src.pipeline import MarketMonitorPipeline
from src.ingestion.market_data import MarketDataFetcher
from src.intelligence.ollama_client import OllamaClient
from src.reporting.terminal_viewer import TerminalViewer

console = Console()


def check_environment():
    """Verifica la salud de los servicios configurados (Ollama, carpetas)."""
    TerminalViewer.show_header()
    console.print("[bold yellow]Comprobando entorno del sistema...[/bold yellow]\n")

    # Verificar Ollama
    ollama = OllamaClient()
    if ollama.is_available():
        console.print(f"[green]✔ Ollama activo[/green] en {ollama.host} (Modelo configurado: {ollama.model})")
    else:
        console.print(f"[red]✖ Ollama no responde[/red] en {ollama.host}. Asegúrate de iniciarlo con 'ollama serve'.")

    # Directorio de reportes
    console.print(f"[green]✔ Carpeta de reportes lista:[/green] {settings.reports_dir}")

    # Feeds configurados
    feeds = settings.load_feeds()
    categories = feeds.get("categories", {})
    total_feeds = sum(len(c.get("feeds", [])) for c in categories.values())
    console.print(f"[green]✔ Feeds configurados:[/green] {total_feeds} feeds en {len(categories)} categorías")
    console.print("\n[bold green]Entorno verificado.[/bold green]")


def inspect_ticker(ticker: str):
    """Consulta rápida de métricas técnicas para un símbolo específico."""
    TerminalViewer.show_header()
    console.print(f"[bold cyan]Consultando métricas de mercado para:[/bold cyan] {ticker}")
    fetcher = MarketDataFetcher()
    snap = fetcher.get_snapshot(ticker)
    if not snap:
        console.print(f"[red]No se pudieron obtener datos para el ticker {ticker}.[/red]")
        return

    console.print(f"[bold white]Activo:[/bold white] {snap.ticker} ({snap.name})")
    console.print(f"[bold white]Precio actual:[/bold white] {snap.current_price} {snap.currency} ({snap.change_pct_24h:+.2f}%)")
    if snap.pct_from_52w_high is not None:
        console.print(f"[bold white]Distancia al máximo de 52 sem:[/bold white] {snap.pct_from_52w_high:.1f}%")
    if snap.pct_from_52w_low is not None:
        console.print(f"[bold white]Distancia al mínimo de 52 sem:[/bold white] +{snap.pct_from_52w_low:.1f}%")
    if snap.rsi_14 is not None:
        rsi_color = "red" if snap.rsi_14 < 30 else ("yellow" if snap.rsi_14 > 70 else "green")
        console.print(f"[bold white]RSI (14 períodos):[/bold white] [{rsi_color}]{snap.rsi_14}[/{rsi_color}]")


def main():
    parser = argparse.ArgumentParser(
        description="Monitor del Mercado: Cazador Autónomo de Oportunidades Asimétricas"
    )
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Ejecuta un ciclo completo de escaneo de feeds y evaluación contrarian.",
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        choices=["macro_and_markets", "commodities_and_energy", "crypto_and_alternatives"],
        help="Filtra el escaneo únicamente por una categoría temática.",
    )
    parser.add_argument(
        "--gemini",
        action="store_true",
        help="Usa Google Gemini 2.0 Flash en lugar del modelo Ollama local.",
    )
    parser.add_argument(
        "--check-env",
        action="store_true",
        help="Verifica la conectividad con Ollama y la configuración de feeds.",
    )
    parser.add_argument(
        "--ticker",
        type=str,
        default=None,
        help="Consulta métricas técnicas y precio actual de un símbolo (ej: CL=F, BTC-USD, NVDA).",
    )
    parser.add_argument(
        "--dashboard",
        "--web",
        action="store_true",
        help="Inicia el Dashboard Web interactivo en http://localhost:8520 para ver fichas y operar el bot.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8520,
        help="Puerto para el servidor del Dashboard web (por defecto: 8520 con auto-resolución de conflictos).",
    )
    parser.add_argument(
        "--directive",
        "--prompt",
        type=str,
        default=None,
        help="Directiva personalizada para orientar el escaneo (ej. 'Recomendaciones de Maslatón').",
    )

    args = parser.parse_args()

    if args.check_env:
        check_environment()
        return

    if args.ticker:
        inspect_ticker(args.ticker)
        return

    if args.dashboard:
        from src.dashboard.server import start_dashboard_server
        start_dashboard_server(port=args.port)
        return

    # Si se pasa --scan o no se pasa ningún argumento, ejecutar el escaneo por defecto
    pipeline = MarketMonitorPipeline(use_gemini=args.gemini)
    pipeline.run(category_filter=args.category, custom_directive=args.directive)


if __name__ == "__main__":
    main()

