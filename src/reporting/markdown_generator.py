from datetime import datetime
from pathlib import Path
from typing import Optional

from config import settings
from src.models import AnalysisBatch, OpportunityCard


class MarkdownReportGenerator:
    """Genera reportes ejecutivos en formato Markdown estandarizado."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or settings.reports_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _render_card(self, card: OpportunityCard) -> str:
        """Renderiza una ficha estructurada individual."""
        stop_line = f"- **Stop Loss / Invalidación:** `{card.stop_loss_sugerido}`\n" if card.stop_loss_sugerido else ""
        target_line = f"- **Target Proyectado:** `{card.target_proyectado}`\n" if card.target_proyectado else ""
        sources = "\n".join(f"  - {s}" for s in card.fuentes_relacionadas) if card.fuentes_relacionadas else "  - Monitoreo de flujo informativo"

        schedule_status = "🟢 ABIERTO EN VIVO" if card.mercado_abierto else "🔴 CERRADO"
        schedule_line = f"* **Horario de Mercado ({card.categoria_mercado or 'Argentina UTC-3'}):** `{card.horario_mercado}` ({schedule_status})\n" if card.horario_mercado else ""
        opening_line = f"* **Próxima Apertura Operativa:** `{card.proxima_apertura}` (esperar cotizaciones vivas)\n" if (card.proxima_apertura and not card.mercado_abierto) else ""

        return f"""### 📌 {card.ticker} — {card.asset_name}
* **Clasificación:** `{card.tipo}`
* **Diagnóstico de Sentimiento:** `{card.sentimiento_mercado}`
{schedule_line}{opening_line}* **Score de Asimetría:** **{card.score_asimetria}/10**
* **Ratio Riesgo/Beneficio:** **1 a {card.ratio_riesgo_beneficio:.1f}**
* **Horizonte Temporal:** `{card.horizonte_temporal}`
* **Nivel de Entrada / Acumulación:** `{card.nivel_entrada_sugerido}`
{stop_line}{target_line}
#### 💡 Tesis Contrarian (Psicología de Masas):
> {card.tesis_contrarian}

#### ⚡ Catalizador Detonante:
{card.catalizador_detonante}

#### 🏛️ Soporte Secular y Viento de Cola:
{card.soporte_secular}

#### 🔗 Fuentes / Referencias:
{sources}

---
"""

    def generate_report(self, batch: AnalysisBatch) -> Path:
        """Escribe el reporte completo en carpetas por fecha y retorna la ruta del archivo generado."""
        import re

        generated_at = datetime.now()
        date_str = generated_at.strftime("%Y-%m-%d")
        time_str = generated_at.strftime("%H%M%S%f")

        # 1. Crear subcarpeta por fecha: reportes/YYYY-MM-DD/
        date_folder = self.output_dir / date_str
        date_folder.mkdir(parents=True, exist_ok=True)

        # 2. Asignar modo y nombre representativo
        if batch.directiva_personalizada and batch.directiva_personalizada.strip():
            batch.modo_escaneo = "BUSQUEDA_ESPECIFICA"
            slug = re.sub(r"[^a-zA-Z0-9ñÑ]+", "_", batch.directiva_personalizada.strip()).strip("_")[:25].lower()
            slug = slug or "directiva"
            filename = f"ESPECIFICO_{slug}_{date_str}_{time_str}.md"
            modo_label = f"🎯 BÚSQUEDA ESPECÍFICA: \"{batch.directiva_personalizada}\""
        else:
            batch.modo_escaneo = "RADAR_AUTONOMO"
            filename = f"RADAR_{date_str}_{time_str}.md"
            modo_label = "🛰️ RADAR AUTÓNOMO"

        report_path = date_folder / filename
        suffix = 2
        while report_path.exists():
            report_path = date_folder / f"{Path(filename).stem}_{suffix}{Path(filename).suffix}"
            suffix += 1

        pct_noise = (
            (batch.total_ruido_descartado / batch.total_noticias_analizadas * 100.0)
            if batch.total_noticias_analizadas > 0
            else 0.0
        )

        directive_line = f"**Directiva Especial:** {batch.directiva_personalizada}  \n" if batch.directiva_personalizada else ""

        md_content = f"""# 🦅 Monitor del Mercado — Reporte de Inteligencia Contrarian
**Modo de Escaneo:** `{modo_label}`  
**Motor Evaluador:** `{batch.motor_evaluador}`  
**Fecha de Emisión:** {batch.timestamp}  
**Vigencia Táctica:** 🟢 VIGENTE (Validez estimada: {batch.horas_vigencia} horas)  
{directive_line}**Misión:** Detección de oportunidades de alta asimetría matemática ($R/B \\ge 1:3$) y capitulaciones de mercado.

---


## 📊 Métricas del Escaneo
| Métrica | Valor |
| :--- | :--- |
| **Eventos / Noticias Ingestadas** | {batch.total_noticias_analizadas} |
| **Ruido Mediático Descartado** | {batch.total_ruido_descartado} ({pct_noise:.1f}%) |
| **Oportunidades Asimétricas Detectadas** | {len(batch.oportunidades)} |
| **Alertas de Peligro / Trampas de Mercado** | {len(batch.alertas_peligro)} |

---

## 🧠 Conclusiones Internas y Proceso de Razonamiento
> **Veredicto Ejecutivo:** {batch.sintesis_ejecutiva}

### Deducciones por etapas del motor de IA:
"""
        for idx, concl in enumerate(batch.conclusiones_internas, 1):
            md_content += f"* **Etapa {idx}:** {concl}\n"

        md_content += """
---

## 🎯 1. Fichas de Oportunidad Asimétrica (Capitulación & Valor)
"""

        if batch.oportunidades:
            for card in batch.oportunidades:
                md_content += self._render_card(card)
        else:
            md_content += "_No se detectaron capitulaciones con ratio $R/B \\ge 1:3$ en este ciclo. Disciplina de capital activa: el 100% califica como ruido o sin asimetría suficiente._\n\n---\n"

        md_content += """
## ⚠️ 2. Alertas de Peligro y Trampas de Mercado (Euforia & Techos)
"""

        if batch.alertas_peligro:
            for card in batch.alertas_peligro:
                md_content += self._render_card(card)
        else:
            md_content += "_No se identificaron trampas extremas de euforia activa en las fuentes escaneadas._\n\n---\n"

        # 3. Hoja de Ruta del Operador Novato
        if batch.guia_operador:
            guia = batch.guia_operador
            pasos_md = "\n".join(f"* {p}" for p in guia.checklist_pasos)

            mkt_status_line = ""
            if guia.horario_mercado:
                st_icon = "🟢 ABIERTO" if guia.mercado_abierto else "🔴 CERRADO"
                mkt_status_line = f"> **Estado y Horario ({guia.categoria_mercado or 'Mercado'}):** `{st_icon}` — {guia.horario_mercado}  \n"
            if guia.proxima_apertura and not guia.mercado_abierto:
                mkt_status_line += f"> **Próxima Ventana de Operación:** {guia.proxima_apertura} (Esperar apertura para evitar datos obsoletos / gap)  \n"

            md_content += f"""
## 🧭 3. Hoja de Ruta del Operador (Plan de Acción Paso a Paso para Principiantes)
> **Semáforo de Decisión:** `{guia.estado_semaforo}`  
{mkt_status_line}> **Instrucción Operativa:** {guia.mensaje_principal}

### 📋 Checklist Operativo en Español Llano:
{pasos_md}

### 🛡️ Regla de Supervivencia (Gestión de Riesgo):
> {guia.regla_gestion_riesgo}

### 🧠 Traductor Psicológico de Noticias (Mente Contrarian):
> {guia.consejo_psicologico}

---
"""

        md_content += """
## 📜 Principio de Independencia
> **Aviso:** Monitor del Mercado es un sistema de investigación e inteligencia computacional pura. No ejecuta órdenes de compra/venta ni constituye asesoramiento financiero. Toda decisión de inversión requiere gestión de riesgo personal.
"""


        with open(report_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        return report_path
