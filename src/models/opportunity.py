from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class OpportunityCard(BaseModel):
    """Ficha Estructurada de Oportunidad de Inversión Contrarian."""

    ticker: str = Field(description="Símbolo del activo (ej. BABA, CL=F, BTC-USD, TLT)")
    asset_name: str = Field(description="Nombre descriptivo del activo o materia prima")
    tipo: Literal["Oportunidad Asimétrica", "Trampa de Mercado / Peligro", "Descarte por Ruido"] = Field(
        description="Clasificación contrarian estricta"
    )
    sentimiento_mercado: Literal[
        "Pánico Extremo / Capitulación",
        "Miedo / Incertidumbre",
        "Neutral / Espera",
        "Optimismo Creciente",
        "Euforia Desmedida / Techo de Mercado"
    ] = Field(description="Diagnóstico del sentimiento de la multitud")
    tesis_contrarian: str = Field(
        description="Por qué la multitud mediática está equivocada y qué señales denotan capitulación o techo"
    )
    catalizador_detonante: str = Field(
        description="Evento detonante macro, tasa de interés, pánico informativo o shock temporal"
    )
    soporte_secular: str = Field(
        description="Fundamento de viento de cola a largo plazo: por qué es una caída transitoria y no una quiebra"
    )
    ratio_riesgo_beneficio: float = Field(
        description="Ratio numérico proyectado Riesgo/Beneficio (mínimo 3.0 para Oportunidad Asimétrica)"
    )
    nivel_entrada_sugerido: str = Field(
        description="Rango de precio o zona de acumulación sugerida"
    )
    stop_loss_sugerido: Optional[str] = Field(
        default=None,
        description="Nivel de invalidación de la tesis (stop de protección conceptual)"
    )
    target_proyectado: Optional[str] = Field(
        default=None,
        description="Objetivo de precio o zona de toma de ganancias"
    )
    horizonte_temporal: str = Field(
        description="Plazo estimado de maduración (ej. '1-3 meses', '6-12 meses', '1-2 años')"
    )
    score_asimetria: int = Field(
        ge=1, le=10,
        description="Puntuación de 1 a 10 del potencial asimétrico y convicción contrarian"
    )
    fuentes_relacionadas: List[str] = Field(
        default_factory=list,
        description="Titulares o URLs que respaldan el análisis"
    )


class AnalysisBatch(BaseModel):
    """Contenedor para la salida consolidada del análisis del motor de IA."""

    timestamp: str = Field(description="Fecha y hora de generación")
    total_noticias_analizadas: int = Field(description="Cantidad de eventos procesados")
    total_ruido_descartado: int = Field(description="Cantidad de noticias descartadas por ruido")
    oportunidades: List[OpportunityCard] = Field(
        default_factory=list,
        description="Fichas de oportunidades asimétricas detectadas"
    )
    alertas_peligro: List[OpportunityCard] = Field(
        default_factory=list,
        description="Fichas de trampas de mercado o euforia peligrosa detectadas"
    )
    conclusiones_internas: List[str] = Field(
        default_factory=list,
        description="Conclusiones intermedias de pensamiento obligatorio generadas por la IA"
    )
    sintesis_ejecutiva: str = Field(
        default="",
        description="Veredicto final consolidado del ciclo de escaneo"
    )
    directiva_personalizada: Optional[str] = Field(
        default=None,
        description="Directiva o enfoque temático solicitado por el usuario"
    )
    guia_operador: Optional["GuiaOperador"] = Field(
        default=None,
        description="Plan de acción paso a paso para el operador novato"
    )


class GuiaOperador(BaseModel):
    """Plan de acción práctico y directo para el operador humano novato."""

    estado_semaforo: Literal["OPERAR CON CAUTELA", "ESPERAR / NO OPERAR", "ALERTA DE PELIGRO"] = Field(
        description="Semáforo de acción directa"
    )
    mensaje_principal: str = Field(
        description="Instrucción en lenguaje cotidiano sin tecnicismos"
    )
    checklist_pasos: List[str] = Field(
        default_factory=list,
        description="Pasos concretos que debe ejecutar el operador"
    )
    regla_gestion_riesgo: str = Field(
        description="Regla de oro de supervivencia de capital para novatos"
    )
    consejo_psicologico: str = Field(
        description="Traducción psicológica de las noticias para no dejarse llevar por el miedo o FOMO"
    )

