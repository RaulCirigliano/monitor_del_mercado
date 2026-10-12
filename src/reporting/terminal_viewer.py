from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.models import AnalysisBatch, OpportunityCard

console = Console()


class TerminalViewer:
    """Visualizador interactivo para la terminal con formato enriquecido."""

    @staticmethod
    def show_header():
        """Muestra el banner de inicio del monitor."""
        title = Text("🦅 MONITOR DEL MERCADO", style="bold cyan")
        subtitle = Text("Cazador Autónomo de Oportunidades Asimétricas", style="italic white")
        console.print(Panel(Text.assemble(title, "\n", subtitle), border_style="cyan", expand=False))

    @staticmethod
    def show_summary_table(batch: AnalysisBatch):
        """Muestra la tabla resumen de métricas del escaneo."""
        table = Table(title="[bold yellow]Resultados del Escaneo[/bold yellow]", border_style="dim")
        table.add_column("Métrica", style="white")
        table.add_column("Valor", style="bold green", justify="right")

        pct_noise = (
            (batch.total_ruido_descartado / batch.total_noticias_analizadas * 100.0)
            if batch.total_noticias_analizadas > 0
            else 0.0
        )

        table.add_row("Noticias / Eventos Procesados", str(batch.total_noticias_analizadas))
        table.add_row("Ruido Descartado", f"{batch.total_ruido_descartado} ({pct_noise:.1f}%)")
        table.add_row("Oportunidades Asimétricas (R/B ≥ 1:3)", str(len(batch.oportunidades)))
        table.add_row("Alertas de Trampas de Mercado", str(len(batch.alertas_peligro)))

        console.print(table)
        console.print()

    @staticmethod
    def show_conclusions(batch: AnalysisBatch):
        """Muestra el panel de conclusiones internas y síntesis obligatoria."""
        if batch.conclusiones_internas or batch.sintesis_ejecutiva:
            content = f"[bold white]{batch.sintesis_ejecutiva}[/bold white]\n"
            if len(batch.conclusiones_internas) > 1:
                content += "\n[dim]" + "\n".join(f"• {c}" for c in batch.conclusiones_internas[:3]) + "[/dim]"
            console.print(
                Panel(
                    content.strip(),
                    title="🧠 [bold yellow]Veredicto & Conclusiones Internas (IA)[/bold yellow]",
                    border_style="yellow",
                )
            )
            console.print()

    @staticmethod
    def show_card(card: OpportunityCard):
        """Muestra una ficha individual en formato de panel de terminal."""
        is_opportunity = card.tipo == "Oportunidad Asimétrica"
        border = "green" if is_opportunity else "red"
        icon = "🎯" if is_opportunity else "⚠️"

        content = f"""[bold]Activo:[/bold] {card.ticker} ({card.asset_name})
[bold]Sentimiento:[/bold] {card.sentimiento_mercado}
[bold]Ratio R/B:[/bold] 1 a {card.ratio_riesgo_beneficio:.1f} | [bold]Score:[/bold] {card.score_asimetria}/10 | [bold]Plazo:[/bold] {card.horizonte_temporal}
[bold]Entrada Sugerida:[/bold] {card.nivel_entrada_sugerido}

[bold yellow]Tesis Contrarian:[/bold yellow]
{card.tesis_contrarian}

[bold cyan]Catalizador:[/bold cyan] {card.catalizador_detonante}
[bold magenta]Soporte Secular:[/bold magenta] {card.soporte_secular}"""

        console.print(Panel(content, title=f"{icon} [bold]{card.tipo}: {card.ticker}[/bold]", border_style=border))

    @staticmethod
    def show_operator_guide(batch: AnalysisBatch):
        """Muestra la hoja de ruta práctica para el operador en terminal."""
        if not batch.guia_operador:
            return

        guia = batch.guia_operador
        color = "green" if "OPERAR" in guia.estado_semaforo else ("red" if "PELIGRO" in guia.estado_semaforo else "yellow")
        pasos_str = "\n".join(f"  [cyan]✔[/cyan] {p}" for p in guia.checklist_pasos)

        content = f"""[bold]Semáforo:[/bold] [{color}]{guia.estado_semaforo}[/{color}]
[bold]Instrucción:[/bold] {guia.mensaje_principal}

[bold underline]Checklist Paso a Paso:[/bold underline]
{pasos_str}

[bold green]🛡️ Gestión de Riesgo:[/bold green] {guia.regla_gestion_riesgo}
[bold magenta]🧠 Mente Contrarian:[/bold magenta] {guia.consejo_psicologico}"""

        console.print(Panel(content, title="🧭 [bold]HOJA DE RUTA DEL OPERADOR (GUÍA PARA NOVATOS)[/bold]", border_style=color))

    @staticmethod
    def show_report_saved(path: Path):
        """Informa sobre el archivo de reporte generado."""
        console.print(f"[bold green]✔ Reporte guardado con éxito en:[/bold green] [underline]{path}[/underline]\n")

