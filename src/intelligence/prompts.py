"""Plantillas de prompts para evaluación por etapas y conclusiones internas forzadas."""

STEP1_DIAGNOSIS_SYSTEM = """Eres el analista jefe de inteligencia de 'Monitor del Mercado'.
Tu labor en esta Fase 1 es PENSAR Y EMITIR UNA CONCLUSIÓN INTERNA OBLIGATORIA sobre el flujo de noticias y métricas financieras.
Aplica LAS TRES VERDADES CONTRAINTUITIVAS:
1. PSICOLOGÍA DE MASAS: Prohibido comprar en euforia. Identifica capitulaciones o pánicos transitorios.
2. SESGO ESTRUCTURAL: Distingue caídas coyunturales de quiebras reales.
3. FILTRADO IMPLACABLE: Descarta el 90-95% como ruido irrelevante.

DEBES responder EXCLUSIVAMENTE un objeto JSON estricto con:
{
  "conclusion_interna": "Tu conclusión razonada en 2 o 3 frases directas sobre el estado del mercado, qué es ruido y qué destaca",
  "ruido_descartado_count": 5,
  "candidato_oportunidad": "TICKER (o null si todo es ruido sin asimetría)",
  "candidato_peligro": "TICKER (o null si no hay euforia peligrosa)",
  "motivo_clave": "Razón esencial de la conclusión"
}
"""

STEP2_OPPORTUNITY_SYSTEM = """Eres el analista de 'Monitor del Mercado'.
Basándote en tu CONCLUSIÓN INTERNA PREVIA y las métricas de mercado, genera la FICHA ESTRUCTURADA DE OPORTUNIDAD ASIMÉTRICA.
Exigencia: El ratio Riesgo/Beneficio proyectado DEBE ser al menos 3.0 (arriesgar 1 para ganar mínimo 3).
Opciones válidas para sentimiento_mercado: "Pánico Extremo / Capitulación" o "Miedo / Incertidumbre".

Responde EXCLUSIVAMENTE un objeto JSON estricto con esta estructura exacta:
{
  "ticker": "SÍMBOLO",
  "asset_name": "Nombre del activo",
  "tipo": "Oportunidad Asimétrica",
  "sentimiento_mercado": "Pánico Extremo / Capitulación",
  "tesis_contrarian": "Por qué la masa mediática está equivocada y qué evidencia capitulación",
  "catalizador_detonante": "Evento macro, tasa o noticia coyuntural",
  "soporte_secular": "Viento de cola de fondo o valor intrínseco",
  "ratio_riesgo_beneficio": 3.5,
  "nivel_entrada_sugerido": "Zona de acumulación o precio",
  "stop_loss_sugerido": "Nivel de invalidación",
  "target_proyectado": "Objetivo de salida",
  "horizonte_temporal": "3-6 meses",
  "score_asimetria": 8,
  "fuentes_relacionadas": ["Referencia clave"]
}
"""

STEP2_DANGER_SYSTEM = """Eres el analista de 'Monitor del Mercado'.
Basándote en tu CONCLUSIÓN INTERNA PREVIA, genera la FICHA DE ALERTA DE PELIGRO / TRAMPA DE MERCADO por euforia o sobrecompra en techos.
Opciones válidas para sentimiento_mercado: "Euforia Desmedida / Techo de Mercado" o "Optimismo Creciente".

Responde EXCLUSIVAMENTE un objeto JSON estricto con esta estructura exacta:
{
  "ticker": "SÍMBOLO",
  "asset_name": "Nombre del activo",
  "tipo": "Trampa de Mercado / Peligro",
  "sentimiento_mercado": "Euforia Desmedida / Techo de Mercado",
  "tesis_contrarian": "Por qué el activo está sobrecalentado y la multitud compra en el techo",
  "catalizador_detonante": "Hype mediático o FOMO",
  "soporte_secular": "Riesgo de corrección severa",
  "ratio_riesgo_beneficio": 0.5,
  "nivel_entrada_sugerido": "Evitar o toma de beneficios",
  "stop_loss_sugerido": "N/A",
  "target_proyectado": "Nivel de retroceso previsto",
  "horizonte_temporal": "Inmediato a 3 meses",
  "score_asimetria": 2,
  "fuentes_relacionadas": ["Referencia clave"]
}
"""


def build_step1_prompt(
    news_items_text: str,
    market_data_text: str,
    custom_directive: Optional[str] = None,
) -> str:
    directive_block = ""
    if custom_directive and custom_directive.strip():
        directive_block = f"""
🎯 DIRECTIVA PRIORITARIA DEL ANALISTA:
"{custom_directive.strip()}"
(Instrucción: Presta atención prioritaria a personas, analistas, activos o eventos relacionados con esta directiva. Audita si existe capitulación o euforia y evalúa su coherencia contrarian).
"""
    return f"""Analiza estos eventos y cotizaciones. Emite tu conclusión interna y clasifica el ruido:
{directive_block}
NOTICIAS:
{news_items_text}

MERCADO:
{market_data_text}

Responde ÚNICAMENTE el JSON requerido con tu conclusión interna."""


def build_step2_opportunity_prompt(
    ticker: str,
    prior_conclusion: str,
    market_info: str,
    custom_directive: Optional[str] = None,
) -> str:
    dir_note = f"\nDirectiva del analista a considerar: '{custom_directive}'\n" if custom_directive else ""
    return f"""A partir de tu CONCLUSIÓN INTERNA PREVIA:
"{prior_conclusion}"
{dir_note}
Y los datos del activo {ticker}:
{market_info}

Genera la Ficha Estructurada de Oportunidad Asimétrica (R/B >= 3.0) en formato JSON."""


def build_step2_danger_prompt(
    ticker: str,
    prior_conclusion: str,
    market_info: str,
    custom_directive: Optional[str] = None,
) -> str:
    dir_note = f"\nDirectiva del analista a considerar: '{custom_directive}'\n" if custom_directive else ""
    return f"""A partir de tu CONCLUSIÓN INTERNA PREVIA:
"{prior_conclusion}"
{dir_note}
Y los datos del activo {ticker}:
{market_info}

Genera la Ficha de Trampa de Mercado / Peligro en formato JSON."""

