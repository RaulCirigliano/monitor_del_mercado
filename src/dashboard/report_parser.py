import re
from pathlib import Path
from typing import Any, Dict, List


def parse_markdown_report(report_path: Path) -> Dict[str, Any]:
    """Parsea un archivo Markdown de reporte y extrae los datos estructurados en formato JSON."""
    if not report_path.exists():
        return {}

    text = report_path.read_text(encoding="utf-8")
    result: Dict[str, Any] = {
        "name": report_path.name,
        "timestamp": "",
        "sintesis_ejecutiva": "",
        "conclusiones_internas": [],
        "oportunidades": [],
        "alertas_peligro": [],
    }

    # Extraer timestamp
    m_time = re.search(r"\*\*Generado:\*\*\s*(.+)", text)
    if m_time:
        result["timestamp"] = m_time.group(1).strip()

    # Extraer veredicto ejecutivo
    m_verdict = re.search(r"> \*\*Veredicto Ejecutivo:\*\*\s*(.+)", text)
    if m_verdict:
        result["sintesis_ejecutiva"] = m_verdict.group(1).strip()

    # Extraer conclusiones por etapa
    steps = re.findall(r"\*\s*\*\*Etapa\s*\d+:\*\*\s*(.+)", text)
    result["conclusiones_internas"] = [s.strip() for s in steps]

    # Extraer tarjetas de oportunidad
    # Cada tarjeta inicia con ### 📌 TICKER — NOMBRE
    card_blocks = re.findall(r"### 📌 ([^\n]+)\n([\s\S]*?)(?=### 📌|## ⚠️|## 📜|$)", text)
    for header, body in card_blocks:
        card = {}
        # Parsear header TICKER — NOMBRE
        if "—" in header:
            parts = header.split("—", 1)
            card["ticker"] = parts[0].strip()
            card["asset_name"] = parts[1].strip()
        else:
            card["ticker"] = header.strip()
            card["asset_name"] = header.strip()

        # Diagnóstico de sentimiento
        m_sent = re.search(r"\* \*\*Diagnóstico de Sentimiento:\*\* `([^`]+)`", body)
        card["sentimiento_mercado"] = m_sent.group(1) if m_sent else "Capitulación"

        # Score
        m_score = re.search(r"\* \*\*Score de Asimetría:\*\* \*\*(\d+)/10\*\*", body)
        card["score_asimetria"] = int(m_score.group(1)) if m_score else 7

        # Ratio R/B
        m_rb = re.search(r"\* \*\*Ratio Riesgo/Beneficio:\*\* \*\*1 a ([\d\.]+)\*\*", body)
        card["ratio_riesgo_beneficio"] = float(m_rb.group(1)) if m_rb else 3.0

        # Horizonte
        m_horiz = re.search(r"\* \*\*Horizonte Temporal:\*\* `([^`]+)`", body)
        card["horizonte_temporal"] = m_horiz.group(1) if m_horiz else "3-6 meses"

        # Nivel de entrada
        m_entry = re.search(r"\* \*\*Nivel de Entrada / Acumulación:\*\* `([^`]+)`", body)
        card["nivel_entrada_sugerido"] = m_entry.group(1) if m_entry else "Zona de soporte"

        # Stop loss
        m_stop = re.search(r"- \*\*Stop Loss / Invalidación:\*\* `([^`]+)`", body)
        card["stop_loss_sugerido"] = m_stop.group(1) if m_stop else None

        # Target
        m_target = re.search(r"- \*\*Target Proyectado:\*\* `([^`]+)`", body)
        card["target_proyectado"] = m_target.group(1) if m_target else None

        # Tesis contrarian
        m_tesis = re.search(r"#### 💡 Tesis Contrarian \(Psicología de Masas\):\n>\s*([^\n]+)", body)
        card["tesis_contrarian"] = m_tesis.group(1).strip() if m_tesis else "Capitulación detectada."

        # Catalizador
        m_cat = re.search(r"#### ⚡ Catalizador Detonante:\n([^\n]+)", body)
        card["catalizador_detonante"] = m_cat.group(1).strip() if m_cat else "Evento de pánico transitorio."

        # Soporte secular
        m_sec = re.search(r"#### 🏛️ Soporte Secular y Viento de Cola:\n([^\n]+)", body)
        card["soporte_secular"] = m_sec.group(1).strip() if m_sec else "Soporte fundamental comprobado."

        result["oportunidades"].append(card)

    return result
