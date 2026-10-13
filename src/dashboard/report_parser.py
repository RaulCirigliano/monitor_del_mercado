import re
from pathlib import Path
from typing import Any, Dict, List


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
    }

    # Extraer timestamp
    m_time = re.search(r"\*\*(?:Fecha de Emisión|Generado):\*\*\s*(.+)", text)
    if m_time:
        result["timestamp"] = m_time.group(1).strip()

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

        # Inteligencia de horarios de mercado para el activo
        from src.ingestion.market_schedule import MarketSchedule
        card_sch = MarketSchedule.check_status(card["ticker"])
        card["mercado_abierto"] = card_sch["mercado_abierto"]
        card["horario_mercado"] = card_sch["horario_argentina"]
        card["proxima_apertura"] = card_sch["proxima_apertura"]
        card["categoria_mercado"] = card_sch["categoria"]
        card["estado_texto"] = card_sch["estado_texto"]
        card["recomendacion_horaria"] = card_sch["recomendacion_horaria"]

        result["oportunidades"].append(card)

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
        ticker_ref = result["oportunidades"][0]["ticker"] if result["oportunidades"] else "SPY"
        sch_info = MarketSchedule.check_status(ticker_ref)
        guia["mercado_abierto"] = sch_info["mercado_abierto"]
        guia["horario_mercado"] = sch_info["horario_argentina"]
        guia["proxima_apertura"] = sch_info["proxima_apertura"]
        guia["categoria_mercado"] = sch_info["categoria"]
        guia["estado_texto"] = sch_info["estado_texto"]
        guia["recomendacion_horaria"] = sch_info["recomendacion_horaria"]
        guia["ticker_referencia"] = ticker_ref

        result["guia_operador"] = guia
    else:
        # Retrocompatibilidad con reportes anteriores
        if result["oportunidades"]:
            opp0 = result["oportunidades"][0]
            sch0 = MarketSchedule.check_status(opp0.get("ticker", "SPY"))
            result["guia_operador"] = {
                "estado_semaforo": "OPERAR CON CAUTELA",
                "mensaje_principal": (
                    f"Existe una oportunidad asimétrica detectada en {opp0.get('ticker')}. "
                    f"Estado: {sch0['estado_texto']}. {sch0['recomendacion_horaria']}"
                ),
                "checklist_pasos": [
                    f"1. VERIFICA EL HORARIO ({sch0['estado_texto']}): El mercado de {opp0.get('ticker')} opera de {sch0['horario_argentina']}. {sch0['proxima_apertura']}.",
                    f"2. ORDEN LÍMITE: Coloca tu orden de compra en {opp0.get('nivel_entrada_sugerido')}.",
                    f"3. STOP LOSS OBLIGATORIO: Pon tu límite de pérdida en {opp0.get('stop_loss_sugerido') or 'zona defensiva'}.",
                    f"4. TAKE PROFIT: Fija tu salida de beneficios en {opp0.get('target_proyectado') or 'zona de target'}.",
                ],
                "regla_gestion_riesgo": "REGLA DEL 1%: Nunca arriesgues más del 1-2% del capital de tu cuenta en una sola operación.",
                "consejo_psicologico": "No compres por impulso ni con mercado cerrado. Espera cotizaciones frescas en vivo.",
                "mercado_abierto": sch0["mercado_abierto"],
                "horario_mercado": sch0["horario_argentina"],
                "proxima_apertura": sch0["proxima_apertura"],
                "categoria_mercado": sch0["categoria"],
                "estado_texto": sch0["estado_texto"],
                "recomendacion_horaria": sch0["recomendacion_horaria"],
                "ticker_referencia": opp0.get("ticker"),
            }
        else:
            sch_spy = MarketSchedule.check_status("SPY")
            result["guia_operador"] = {
                "estado_semaforo": "ESPERAR / NO OPERAR",
                "mensaje_principal": "El 100% de las noticias analizadas son ruido. La decisión más inteligente hoy es no operar.",
                "checklist_pasos": [
                    "1. Mantén tu dinero 100% en liquidez.",
                    "2. No compres activos por aburrimiento o ansiedad.",
                    f"3. Horario central de Wall Street: {sch_spy['horario_argentina']}.",
                ],
                "regla_gestion_riesgo": "No perder dinero en días de ruido es exactamente igual a ganar dinero.",
                "consejo_psicologico": "Los profesionales pasan la mayor parte del tiempo esperando la asimetría correcta.",
                "mercado_abierto": sch_spy["mercado_abierto"],
                "horario_mercado": sch_spy["horario_argentina"],
                "proxima_apertura": sch_spy["proxima_apertura"],
                "categoria_mercado": sch_spy["categoria"],
                "estado_texto": sch_spy["estado_texto"],
                "recomendacion_horaria": sch_spy["recomendacion_horaria"],
                "ticker_referencia": "SPY",
            }

    return result

