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
        gt=0,
        allow_inf_nan=False,
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
    horario_mercado: Optional[str] = Field(
        default=None,
        description="Ventana horaria de negociación oficial en Argentina (UTC-3)"
    )
    mercado_abierto: Optional[bool] = Field(
        default=None,
        description="Estado de apertura en tiempo real"
    )
    proxima_apertura: Optional[str] = Field(
        default=None,
        description="Próxima apertura operativa recomendada para evitar datos congelados"
    )
    categoria_mercado: Optional[str] = Field(
        default=None,
        description="Categoría o tipo de activo según horarios de mercado"
    )
    rsi_14: Optional[float] = Field(default=None, description="RSI(14) al momento de la evaluación")
    z_score_20: Optional[float] = Field(default=None, description="Z-Score(20) al momento de la evaluación")
    pct_from_52w_high: Optional[float] = Field(default=None, description="% de distancia desde el máximo de 52 semanas")
    ema_200: Optional[float] = Field(default=None, description="EMA(200) diaria al momento de la evaluación")
    atr_pct: Optional[float] = Field(default=None, description="ATR(14) porcentual sobre el precio actual")
    rvol_20: Optional[float] = Field(default=None, description="Volumen relativo de 20 períodos")

    @property
    def entry_price_range(self) -> str:
        return self.nivel_entrada_sugerido

    @entry_price_range.setter
    def entry_price_range(self, value: str) -> None:
        self.nivel_entrada_sugerido = value

    @property
    def stop_loss(self) -> Optional[str]:
        return self.stop_loss_sugerido

    @stop_loss.setter
    def stop_loss(self, value: Optional[str]) -> None:
        self.stop_loss_sugerido = value

    @property
    def take_profit(self) -> Optional[str]:
        return self.target_proyectado

    @take_profit.setter
    def take_profit(self, value: Optional[str]) -> None:
        self.target_proyectado = value

    @property
    def risk_reward_ratio(self) -> float:
        return self.ratio_riesgo_beneficio

    @risk_reward_ratio.setter
    def risk_reward_ratio(self, value: float) -> None:
        self.ratio_riesgo_beneficio = value


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
    modo_escaneo: Literal["RADAR_AUTONOMO", "BUSQUEDA_ESPECIFICA"] = Field(
        default="RADAR_AUTONOMO",
        description="Modo bajo el cual se generó el escaneo"
    )
    vigente: bool = Field(
        default=True,
        description="Indica si la tesis del reporte sigue vigente"
    )
    horas_vigencia: int = Field(
        default=48,
        description="Horas de validez táctica estimada para las ideas del reporte"
    )
    guia_operador: Optional["GuiaOperador"] = Field(
        default=None,
        description="Plan de acción paso a paso para el operador novato"
    )
    motor_evaluador: str = Field(
        default="Ollama Local",
        description="Motor de inteligencia: Ollama Local o Antigravity CIO"
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
    horario_mercado: Optional[str] = Field(
        default=None,
        description="Ventana horaria de negociación oficial en Argentina (UTC-3)"
    )
    mercado_abierto: Optional[bool] = Field(
        default=None,
        description="Estado de apertura en tiempo real"
    )
    proxima_apertura: Optional[str] = Field(
        default=None,
        description="Próxima apertura operativa o evento horario para disparar la orden con liquidez viva"
    )
    categoria_mercado: Optional[str] = Field(
        default=None,
        description="Categoría o tipo de activo según horarios de mercado"
    )
    recomendacion_horaria: Optional[str] = Field(
        default=None,
        description="Instrucción antibot y advertencia de gap para novatos"
    )
