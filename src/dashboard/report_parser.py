import re
from pathlib import Path
from typing import Any, Dict, List


def _parse_cards(section: str, card_type: str) -> List[Dict[str, Any]]:
    from src.ingestion.market_schedule import MarketSchedule

    parsed_cards = []
    card_blocks = re.findall(r"### 📌 ([^\n]+)\n([\s\S]*?)(?=### 📌|$)", section)
    for header, body in card_blocks:
        if "—" in header:
            ticker, asset_name = (part.strip() for part in header.split("—", 1))
        else:
            ticker = asset_name = header.strip()

        card: Dict[str, Any] = {"ticker": ticker, "asset_name": asset_name, "tipo": card_type}
        m_sent = re.search(r"\* \*\*Diagnóstico de Sentimiento:\*\* `([^`]+)`", body)
        card["sentimiento_mercado"] = m_sent.group(1) if m_sent else None
        m_score = re.search(r"\* \*\*Score de Asimetría:\*\* \*\*(\d+)/10\*\*", body)
        card["score_asimetria"] = int(m_score.group(1)) if m_score else None
        m_rb = re.search(r"\* \*\*Ratio Riesgo/Beneficio:\*\* \*\*1 a ([\d\.]+)\*\*", body)
        card["ratio_riesgo_beneficio"] = float(m_rb.group(1)) if m_rb else None
        m_horiz = re.search(r"\* \*\*Horizonte Temporal:\*\* `([^`]+)`", body)
        card["horizonte_temporal"] = m_horiz.group(1) if m_horiz else None
        m_entry = re.search(r"\* \*\*Nivel de Entrada / Acumulación:\*\* `([^`]+)`", body)
        card["nivel_entrada_sugerido"] = m_entry.group(1) if m_entry else None
        m_stop = re.search(r"- \*\*Stop Loss / Invalidación:\*\* `([^`]+)`", body)
        card["stop_loss_sugerido"] = m_stop.group(1) if m_stop else None
        m_target = re.search(r"- \*\*Target Proyectado:\*\* `([^`]+)`", body)
        card["target_proyectado"] = m_target.group(1) if m_target else None
        m_tesis = re.search(r"#### 💡 Tesis Contrarian \(Psicología de Masas\):\n>\s*([^\n]+)", body)
        card["tesis_contrarian"] = m_tesis.group(1).strip() if m_tesis else None
        m_cat = re.search(r"#### ⚡ Catalizador Detonante:\n([^\n]+)", body)
        card["catalizador_detonante"] = m_cat.group(1).strip() if m_cat else None
        m_sec = re.search(r"#### 🏛️ Soporte Secular y Viento de Cola:\n([^\n]+)", body)
        card["soporte_secular"] = m_sec.group(1).strip() if m_sec else None

        schedule = MarketSchedule.check_status(ticker)
        card["mercado_abierto"] = schedule["mercado_abierto"]
        card["horario_mercado"] = schedule["horario_argentina"]
        card["proxima_apertura"] = schedule["proxima_apertura"]
        card["categoria_mercado"] = schedule["categoria"]
        card["estado_texto"] = schedule["estado_texto"]
        card["recomendacion_horaria"] = schedule["recomendacion_horaria"]
        parsed_cards.append(card)
    return parsed_cards


def parse_markdown_report(report_path: Path) -> Dict[str, Any]:
    """Parsea un archivo Markdown de reporte y extrae los datos estructurados en formato JSON."""
    if not report_path.exists():
        return {}

    text = report_path.read_text(encoding="utf-8")
    from datetime import datetime


    # Vigencia y relevancia temporal calculada a partir de fecha y hora
    mtime = report_path.stat().st_mtime
    file_dt = datetime.fromtimestamp(mtime)
    hours_old = max(0.0, (datetime.now() - file_dt).total_seconds() / 3600.0)
    es_vigente = hours_old <= 48.0

    # Modo de escaneo
    modo_escaneo = "BUSQUEDA_ESPECIFICA" if report_path.name.startswith("ESPECIFICO_") else "RADAR_AUTONOMO"

    try:
        from config import settings
        rel_path = str(report_path.relative_to(settings.reports_dir))
    except Exception:
        rel_path = report_path.name

    result: Dict[str, Any] = {
        "name": report_path.name,
        "rel_path": rel_path,
        "date_folder": report_path.parent.name if report_path.parent.name != "reportes" else "General",
        "timestamp": "",
        "modo_escaneo": modo_escaneo,
        "es_vigente": es_vigente,
        "horas_antiguedad": round(hours_old, 1),
        "estado_vigencia": "🟢 VIGENTE (Activo)" if es_vigente else "⚪ HISTÓRICO (Caducado)",
        "sintesis_ejecutiva": "",
        "conclusiones_internas": [],
        "oportunidades": [],
        "alertas_peligro": [],
        "directiva_personalizada": None,
        "motor_evaluador": "Ollama Local",
    }

    # Extraer timestamp
    m_time = re.search(r"\*\*(?:Fecha de Emisión|Generado):\*\*\s*(.+)", text)
    if m_time:
        result["timestamp"] = m_time.group(1).strip()

    # Extraer motor evaluador si existe
    m_motor = re.search(r"\*\*Motor Evaluador:\*\*\s*`([^`]+)`", text)
    if m_motor:
        result["motor_evaluador"] = m_motor.group(1).strip()
    elif "Antigravity CIO" in text[:300]:
        result["motor_evaluador"] = "Antigravity CIO"

    # Extraer modo explícito si está en el texto
    m_modo = re.search(r"\*\*Modo de Escaneo:\*\*\s*`([^`]+)`", text)
    if m_modo:
        modo_txt = m_modo.group(1).strip()
        if "BÚSQUEDA ESPECÍFICA" in modo_txt:
            result["modo_escaneo"] = "BUSQUEDA_ESPECIFICA"
        elif "RADAR" in modo_txt:
            result["modo_escaneo"] = "RADAR_AUTONOMO"

    # Extraer directiva especial si existe
    m_dir = re.search(r"\*\*Directiva Especial:\*\*\s*(.+)", text)
    if m_dir:
        result["directiva_personalizada"] = m_dir.group(1).strip()

    # Extraer veredicto ejecutivo
    m_verdict = re.search(r"> \*\*Veredicto Ejecutivo:\*\*\s*(.+)", text)
    if m_verdict:
        result["sintesis_ejecutiva"] = m_verdict.group(1).strip()

    # Extraer conclusiones por etapa
    steps = re.findall(r"\*\s*\*\*Etapa\s*\d+:\*\*\s*(.+)", text)
    result["conclusiones_internas"] = [s.strip() for s in steps]


    opportunity_section = re.search(
        r"## 🎯 1\..*?\n([\s\S]*?)(?=\n## ⚠️ 2\.|$)", text
    )
    danger_section = re.search(
        r"## ⚠️ 2\..*?\n([\s\S]*?)(?=\n## 🧭 3\.|\n## 📜|$)", text
    )
    if opportunity_section:
        result["oportunidades"] = _parse_cards(
            opportunity_section.group(1), "Oportunidad Asimétrica"
        )
    if danger_section:
        result["alertas_peligro"] = _parse_cards(
            danger_section.group(1), "Trampa de Mercado / Peligro"
        )

    from src.ingestion.market_schedule import MarketSchedule

    # Extraer Hoja de Ruta del Operador
    m_semaforo = re.search(r"> \*\*Semáforo de Decisión:\*\*\s*`([^`]+)`", text)
    if m_semaforo:
        guia = {
            "estado_semaforo": m_semaforo.group(1).strip(),
            "mensaje_principal": "",
            "checklist_pasos": [],
            "regla_gestion_riesgo": "",
            "consejo_psicologico": "",
        }
        m_inst = re.search(r"> \*\*Instrucción Operativa:\*\*\s*(.+)", text)
        if m_inst:
            guia["mensaje_principal"] = m_inst.group(1).strip()

        # Extraer pasos del checklist
        m_pasos = re.findall(r"\*\s*(\d+\..+)", text)
        guia["checklist_pasos"] = [p.strip() for p in m_pasos]

        # Extraer regla de riesgo
        m_riesgo = re.search(r"### 🛡️ Regla de Supervivencia \(Gestión de Riesgo\):\n>\s*([^\n]+)", text)
        if m_riesgo:
            guia["regla_gestion_riesgo"] = m_riesgo.group(1).strip()

        # Extraer consejo psicológico
        m_psico = re.search(r"### 🧠 Traductor Psicológico de Noticias \(Mente Contrarian\):\n>\s*([^\n]+)", text)
        if m_psico:
            guia["consejo_psicologico"] = m_psico.group(1).strip()

        # Calcular o asignar horario de mercado en vivo
        cards = result["oportunidades"] or result["alertas_peligro"]
        ticker_ref = cards[0]["ticker"] if cards else "SPY"
        sch_info = MarketSchedule.check_status(ticker_ref)
        guia["mercado_abierto"] = sch_info["mercado_abierto"]
        guia["horario_mercado"] = sch_info["horario_argentina"]
        guia["proxima_apertura"] = sch_info["proxima_apertura"]
        guia["categoria_mercado"] = sch_info["categoria"]
        guia["estado_texto"] = sch_info["estado_texto"]
        guia["recomendacion_horaria"] = sch_info["recomendacion_horaria"]
        guia["ticker_referencia"] = ticker_ref

        result["guia_operador"] = guia
    return result
