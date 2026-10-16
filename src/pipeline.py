from datetime import datetime
from typing import Dict, List, Optional
from rich.console import Console

from src.ingestion import RSSCollector, MarketDataFetcher
from src.intelligence import ContrarianEvaluator
from src.reporting import MarkdownReportGenerator, TerminalViewer
from src.models import AnalysisBatch, AssetSnapshot, NewsItem

console = Console()


class MarketMonitorPipeline:
    """Orquestador completo del flujo de investigación y evaluación contrarian."""

    # Tickers referentes del universo operable de trading_ollama (se completan bajo demanda según noticias)
    KEY_TICKERS = [
        "^GSPC",
        "SPY",
        "QQQ",
        "CL=F",
        "GC=F",
        "BTC-USD",
        "TLT",
        "NVDA",
        "BABA",
        "YPFD.BA",
        "GGAL.BA",
    ]
    BENCHMARK_TICKERS = KEY_TICKERS

    def __init__(self, use_gemini: bool = False):
        self.collector = RSSCollector()
        self.market_fetcher = MarketDataFetcher()
        self.evaluator = ContrarianEvaluator(use_gemini=use_gemini)
        self.report_generator = MarkdownReportGenerator()

    @classmethod
    def _ordered_tickers(cls, news_items: List[NewsItem], limit: int = 15) -> List[str]:
        ordered = []
        seen = set()
        for item in news_items:
            for ticker in item.tickers_detected:
                if ticker not in seen:
                    seen.add(ticker)
                    ordered.append(ticker)
        for ticker in cls.KEY_TICKERS:
            if ticker not in seen:
                seen.add(ticker)
                ordered.append(ticker)
        return ordered[:limit]

    def run(
        self,
        category_filter: Optional[str] = None,
        custom_directive: Optional[str] = None,
    ) -> AnalysisBatch:
        """Ejecuta el ciclo completo de escaneo e inteligencia."""
        TerminalViewer.show_header()

        if custom_directive and custom_directive.strip():
            console.print(f"[bold magenta]🎯 Directiva personalizada activa:[/bold magenta] [white]'{custom_directive.strip()}'[/white]")

        # 1. Ingesta RSS (con búsqueda dirigida si hay directiva)
        with console.status("[bold green]Recolectando feeds RSS y filtrando ruido inicial...", spinner="dots"):
            news_items = self.collector.collect_all(
                category_filter=category_filter,
                custom_query=custom_directive,
            )

        console.print(f"[bold cyan]ℹ Noticias ingestadas y limpias tras descarte inicial:[/bold cyan] {len(news_items)}")

        if not news_items:
            console.print("[yellow]No se encontraron noticias recientes o no superaron los filtros de descarte.[/yellow]")
            batch = AnalysisBatch(
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                total_noticias_analizadas=0,
                total_ruido_descartado=0,
                oportunidades=[],
                alertas_peligro=[],
                directiva_personalizada=custom_directive,
            )
            report_path = self.report_generator.generate_report(batch)
            TerminalViewer.show_report_saved(report_path)
            return batch

        # 2. Extracción y consulta de tickers
        detected_tickers = self._ordered_tickers(news_items)

        snapshots: Dict[str, AssetSnapshot] = {}
        with console.status(f"[bold green]Consultando cotizaciones de {min(len(detected_tickers), 15)} activos en yfinance...", spinner="dots"):
            # Consultamos un límite razonable de tickers para no saturar
            for t in detected_tickers[:15]:
                snap = self.market_fetcher.get_snapshot(t)
                if snap:
                    snapshots[t] = snap

        console.print(f"[bold cyan]ℹ Cotizaciones y métricas técnicas recopiladas:[/bold cyan] {len(snapshots)} activos")

        # 3. Evaluación con IA Contrarian
        with console.status("[bold magenta]Evaluando psicología de masas y asimetría matemática con IA...", spinner="dots"):
            batch = self.evaluator.evaluate(
                news_items, snapshots, custom_directive=custom_directive
            )


        # 4. Generación de Reporte Markdown
        report_path = self.report_generator.generate_report(batch)

        # 5. Visualización en Terminal
        TerminalViewer.show_summary_table(batch)
        TerminalViewer.show_conclusions(batch)

        if batch.oportunidades:
            console.print("[bold green]=== OPORTUNIDADES ASIMÉTRICAS DETECTADAS ===[/bold green]")
            for card in batch.oportunidades:
                TerminalViewer.show_card(card)

        if batch.alertas_peligro:
            console.print("[bold red]=== ALERTAS DE TRAMPAS DE MERCADO / EUFORIA ===[/bold red]")
            for card in batch.alertas_peligro:
                TerminalViewer.show_card(card)

        TerminalViewer.show_operator_guide(batch)
        TerminalViewer.show_report_saved(report_path)

        return batch
