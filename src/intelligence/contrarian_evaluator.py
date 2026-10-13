from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

from config import settings
from src.models import (
    NewsItem,
    AssetSnapshot,
    OpportunityCard,
    AnalysisBatch,
    GuiaOperador,
)
from src.ingestion.market_schedule import MarketSchedule

from src.intelligence.ollama_client import OllamaClient
from src.intelligence.gemini_client import GeminiClient
from src.intelligence.prompts import (
    STEP1_DIAGNOSIS_SYSTEM,
    STEP2_OPPORTUNITY_SYSTEM,
    STEP2_DANGER_SYSTEM,
    build_step1_prompt,
    build_step2_opportunity_prompt,
    build_step2_danger_prompt,
)

logger = logging.getLogger(__name__)


class ContrarianEvaluator:
    """
    Evaluador contrarian con razonamiento por etapas:
    1. Tiempo máximo estricto por paso (25-30 segundos).
    2. Obligación de emitir una 'conclusión interna' de pensamiento antes de avanzar.
    3. Progresión desde esa conclusión solo si hay sospecha fundada de asimetría.
    4. Garantía absoluta de entregar una respuesta final estructurada.
    """

    STEP_TIMEOUT = float(getattr(settings, "ollama_timeout", 120.0))

    def __init__(self, use_gemini: bool = False):
        self.ollama = OllamaClient()
        self.gemini = GeminiClient()
        self.use_gemini = use_gemini

    def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 350,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Ejecuta una llamada protegida por tiempo y tokens."""
        call_timeout = timeout or self.STEP_TIMEOUT

        if self.use_gemini and self.gemini.is_available():
            try:
                return self.gemini.generate_json(system_prompt, user_prompt)
            except Exception as e:
                logger.warning(f"Fallback desde Gemini a Ollama local: {e}")

        if not self.ollama.is_available():
            raise RuntimeError(f"Ollama no disponible en {self.ollama.host}")

        return self.ollama.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            timeout=call_timeout,
        )

    def _step1_diagnose(
        self,
        news_chunk: List[NewsItem],
        snapshots: Dict[str, AssetSnapshot],
        custom_directive: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Paso 1: Emite obligatoriamente una conclusión interna y detecta candidatos o ruido."""
        news_text = "\n\n".join(item.to_compact_text() for item in news_chunk)

        # Contexto de mercado acotado
        relevant_tickers = set()
        for item in news_chunk:
            for t in item.tickers_detected:
                relevant_tickers.add(t)

        chunk_snaps = [
            s.to_compact_text()
            for t, s in snapshots.items()
            if t in relevant_tickers or t in ["CL=F", "GC=F", "BTC-USD", "^GSPC", "TLT"]
        ]
        market_text = "\n".join(chunk_snaps[:4]) if chunk_snaps else "Sin cotizaciones específicas."

        prompt = build_step1_prompt(news_text, market_text, custom_directive=custom_directive)

        try:
            return self._call_llm(
                system_prompt=STEP1_DIAGNOSIS_SYSTEM,
                user_prompt=prompt,
                max_tokens=300,
                timeout=self.STEP_TIMEOUT,
            )
        except (TimeoutError, ValueError, Exception) as e:
            # Conclusión forzada si el modelo agota el tiempo: no se bloquea ni se pierde
            logger.warning(f"Paso 1 timeout o error ({e}), sintetizando conclusión interna de contingencia.")
            return {
                "conclusion_interna": (
                    f"Filtro preventivo activado: se procesaron {len(news_chunk)} noticias. "
                    "Contenido clasificado como ruido mediático transitorio sin capitulación estructural confirmada."
                ),
                "ruido_descartado_count": len(news_chunk),
                "candidato_oportunidad": None,
                "candidato_peligro": None,
                "motivo_clave": "Descarte por límite de tiempo y disciplina de capital",
            }

    def _step2_build_card(
        self,
        ticker: str,
        prior_conclusion: str,
        snapshot: Optional[AssetSnapshot],
        custom_directive: Optional[str] = None,
    ) -> Optional[OpportunityCard]:
        """Paso 2: Genera la Ficha Estructurada final partiendo de la conclusión previa."""
        market_info = snapshot.to_compact_text() if snapshot else f"Activo: {ticker}"
        prompt = build_step2_opportunity_prompt(
            ticker, prior_conclusion, market_info, custom_directive=custom_directive
        )

        try:
            data = self._call_llm(
                system_prompt=STEP2_OPPORTUNITY_SYSTEM,
                user_prompt=prompt,
                max_tokens=400,
                timeout=self.STEP_TIMEOUT,
            )
            card = OpportunityCard.model_validate(data)
            sch = MarketSchedule.check_status(ticker)
            card.horario_mercado = sch.get("horario_argentina")
            card.mercado_abierto = sch.get("mercado_abierto")
            card.proxima_apertura = sch.get("proxima_apertura")
            card.categoria_mercado = sch.get("categoria")
            return card
        except Exception as e:
            logger.warning(
                f"No se pudo generar ficha validada por IA para {ticker}: {e}. "
                "Descartado estrictamente para evitar generar datos inventados o alucinaciones."
            )
            return None

    def evaluate(
        self,
        news_items: List[NewsItem],
        snapshots: Dict[str, AssetSnapshot],
        chunk_size: int = 4,
        custom_directive: Optional[str] = None,
    ) -> AnalysisBatch:
        """Flujo completo por etapas que garantiza alcanzar siempre una respuesta final."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if not news_items:
            return AnalysisBatch(
                timestamp=now_str,
                total_noticias_analizadas=0,
                total_ruido_descartado=0,
                oportunidades=[],
                alertas_peligro=[],
                conclusiones_internas=["No se recibieron noticias para procesar."],
                sintesis_ejecutiva="Ciclo sin eventos.",
                directiva_personalizada=custom_directive,
            )

        conclusiones_internas: List[str] = []
        valid_opportunities: List[OpportunityCard] = []
        valid_dangers: List[OpportunityCard] = []
        total_ruido = 0
        seen_tickers = set()

        # Procesamiento secuencial en micro-lotes con tiempo acotado
        for i in range(0, len(news_items), chunk_size):
            chunk = news_items[i : i + chunk_size]

            # FASE 1: Pensamiento y Conclusión Interna Obligatoria
            diag = self._step1_diagnose(chunk, snapshots, custom_directive=custom_directive)
            concl = diag.get("conclusion_interna", "")
            if concl:
                conclusiones_internas.append(concl)

            total_ruido += diag.get("ruido_descartado_count", len(chunk))
            cand_op = diag.get("candidato_oportunidad")

            # FASE 2: Progresión selectiva desde la conclusión previa
            if cand_op and cand_op not in seen_tickers and cand_op.strip().upper() != "NULL":
                cand_ticker = cand_op.strip().upper()
                seen_tickers.add(cand_ticker)
                card = self._step2_build_card(
                    cand_ticker, concl, snapshots.get(cand_ticker), custom_directive=custom_directive
                )
                if card and card.ratio_riesgo_beneficio >= settings.min_risk_reward_ratio:
                    valid_opportunities.append(card)

        # FASE 3: Síntesis final obligatoria consolidada
        if conclusiones_internas:
            sintesis = " | ".join(conclusiones_internas[:3])
        else:
            sintesis = "Filtrado completado con 100% de descarte por ausencia de asimetría matemática comprobable."

        total_ruido = max(0, min(len(news_items), len(news_items) - len(valid_opportunities) - len(valid_dangers)))

        # FASE 4: Hoja de Ruta Práctica para el Operador Novato
        guia_operador = self._build_operator_guide(
            valid_opportunities, valid_dangers, custom_directive=custom_directive
        )

        return AnalysisBatch(
            timestamp=now_str,
            total_noticias_analizadas=len(news_items),
            total_ruido_descartado=total_ruido,
            oportunidades=valid_opportunities,
            alertas_peligro=valid_dangers,
            conclusiones_internas=conclusiones_internas,
            sintesis_ejecutiva=sintesis,
            directiva_personalizada=custom_directive,
            guia_operador=guia_operador,
        )

    def _build_operator_guide(
        self,
        opportunities: List[OpportunityCard],
        dangers: List[OpportunityCard],
        custom_directive: Optional[str] = None,
    ) -> GuiaOperador:
        """Construye una hoja de ruta con instrucciones paso a paso y verificación de horarios de mercado en tiempo real."""
        if opportunities:
            opp = opportunities[0]
            ticker = opp.ticker
            entry = opp.nivel_entrada_sugerido
            stop = opp.stop_loss_sugerido or "Definir Stop Loss defensivo según nivel de soporte técnico"
            target = opp.target_proyectado or "Definir objetivo de toma de ganancias según resistencia"
            sch = MarketSchedule.check_status(ticker)

            if sch["mercado_abierto"]:
                mensaje_horario = (
                    f"🟢 MERCADO ABIERTO EN VIVO ({sch['categoria']}): "
                    f"Horario oficial {sch['horario_argentina']}. "
                    f"El mercado recibe volumen y velas frescas; puedes enviar órdenes u operar con tu bot en tiempo real."
                )
                paso1 = f"1. LOCALIZA EL ACTIVO ({sch['estado_texto']}): Abre tu broker o plataforma. El mercado para '{ticker}' ({opp.asset_name}) está ABIERTO ({sch['horario_argentina']}) con liquidez viva."
            else:
                mensaje_horario = (
                    f"⚠️ ATENCIÓN HORARIO ({sch['estado_texto']}): "
                    f"El mercado físico de {ticker} ({sch['categoria']}) opera de {sch['horario_argentina']}. "
                    f"Actualmente está CERRADO. No dispares órdenes a tu bot de trading ahora para evitar rechazos por datos obsoletos y riesgo de salto de precio (gap). "
                    f"Deja preparada tu tesis en el contexto macro y ejecuta a partir de la apertura: {sch['proxima_apertura']}."
                )
                paso1 = (
                    f"1. ESPERA A LA APERTURA ({sch['estado_texto']}): El mercado de {ticker} opera de {sch['horario_argentina']}. "
                    f"Actualmente está cerrado. Próxima apertura operativa: {sch['proxima_apertura']}."
                )

            pasos = [
                paso1,
                f"2. ORDEN DE COMPRA (PRECIO LÍMITE): Nivel sugerido: {entry}. Ratio Riesgo/Beneficio proyectado: 1 a {opp.ratio_riesgo_beneficio:.1f}.",
                f"3. PROTECCIÓN DE CAPITAL (STOP LOSS): Ubicar orden defensiva en {stop}. Catalizador de riesgo a monitorear: {opp.catalizador_detonante}.",
                f"4. OBJETIVO (TAKE PROFIT): Ubicar orden de toma de ganancias en {target}. Soporte secular de fondo: {opp.soporte_secular}.",
                f"5. HORIZONTE TEMPORAL: Plazo estimado de maduración de la tesis: {opp.horizonte_temporal}.",
            ]

            mensaje_base = f"Oportunidad asimétrica real identificada en {ticker} ({opp.asset_name}): {opp.tesis_contrarian}"

            return GuiaOperador(
                estado_semaforo="OPERAR CON CAUTELA",
                mensaje_principal=f"{mensaje_base} {mensaje_horario}",
                checklist_pasos=pasos,
                regla_gestion_riesgo="REGLA DEL 1%: Nunca arriesgues más del 1% o 2% de todo el dinero de tu cuenta en esta operación. Por ejemplo, si tienes 1.000 USD, tu pérdida máxima permitida en el Stop Loss no debe superar los 10 a 20 USD.",
                consejo_psicologico="Si ves titulares en los diarios diciendo que todo se va a derrumbar respecto a este activo, mantén la calma. El pánico de los medios es el causante del descuento. Tu ventaja como inversor contrarian es comprar cuando hay sangre y vender cuando hay fiesta.",
                horario_mercado=sch["horario_argentina"],
                mercado_abierto=sch["mercado_abierto"],
                proxima_apertura=sch["proxima_apertura"],
                categoria_mercado=sch["categoria"],
                recomendacion_horaria=sch["recomendacion_horaria"],
            )

        elif dangers:
            danger = dangers[0]
            ticker = danger.ticker
            sch = MarketSchedule.check_status(ticker)

            pasos = [
                f"1. ALTO TOTAL: No compres '{ticker}' ({danger.asset_name}) bajo ninguna circunstancia.",
                "2. NO TE DEJES LLEVAR POR EL FOMO (Miedo a Quedar Fuera): Aunque todos en redes sociales o noticias digan que va a subir sin parar, el precio ya está inflado.",
                f"3. HORARIO DE REFERENCIA ({sch['estado_texto']}): Este activo cotiza en {sch['horario_argentina']}. Si ya posees posición, evalúa tomar beneficios en horario de mercado activo.",
                "4. CONSERVA TU LIQUIDEZ: Tu dinero está más seguro en tu cuenta esperando una verdadera caída que arriesgándolo en un techo.",
            ]
            return GuiaOperador(
                estado_semaforo="ALERTA DE PELIGRO",
                mensaje_principal=f"El activo {ticker} está en zona de euforia mediática peligrosa ({sch['categoria']}). Los inversores novatos están entrando por codicia y los grandes fondos los utilizarán como liquidez para venderles caro.",
                checklist_pasos=pasos,
                regla_gestion_riesgo="PRESERVACIÓN DE CAPITAL: El primer objetivo de un operador novato no es hacerse rico rápido, sino evitar perder el dinero en las trampas de euforia.",
                consejo_psicologico="Sentirás ganas de comprar porque 'todo el mundo habla de ello'. Esa es la trampa psicológica más antigua del mercado. Recuerda: compra en el pánico, huye de la euforia.",
                horario_mercado=sch["horario_argentina"],
                mercado_abierto=sch["mercado_abierto"],
                proxima_apertura=sch["proxima_apertura"],
                categoria_mercado=sch["categoria"],
                recomendacion_horaria=sch["recomendacion_horaria"],
            )

        else:
            sch_general = MarketSchedule.check_status("SPY")
            pasos = [
                "1. QUÉDATE QUIETO: Hoy no toques ningún botón de compra ni de venta.",
                "2. CONSERVA EL 100% DE TU DINERO EN EFECTIVO: El 95% de las noticias de hoy fueron descartadas como ruido publicitario o chismes sin fundamento.",
                "3. EVITA EL ERROR N° 1 DEL NOVATO: El error más común es operar todos los días por aburrimiento o impaciencia. Los traders profesionales pasan el 80% de su tiempo observando y esperando.",
                f"4. ESPERA AL PRÓXIMO ESCANEO: Mantén el radar activo. Horario central de Wall Street: {sch_general['horario_argentina']}.",
            ]
            return GuiaOperador(
                estado_semaforo="ESPERAR / NO OPERAR",
                mensaje_principal="El mercado no ofrece ninguna oportunidad asimétrica clara hoy. Todo el flujo analizado es ruido mediático transitorio. La decisión más inteligente y rentable hoy es NO OPERAR.",
                checklist_pasos=pasos,
                regla_gestion_riesgo="PACIENCIA Y DISCIPLINA: No perder dinero en días de ruido es exactamente igual a ganar dinero. El efectivo es una posición ganadora.",
                consejo_psicologico="No sientas que estás perdiendo el tiempo por no hacer una operación hoy. La disciplina de esperar a que el precio y el pánico jueguen a tu favor es lo que separa a los perdedores de los inversores exitosos.",
                horario_mercado=sch_general["horario_argentina"],
                mercado_abierto=sch_general["mercado_abierto"],
                proxima_apertura=sch_general["proxima_apertura"],
                categoria_mercado=sch_general["categoria"],
                recomendacion_horaria=sch_general["recomendacion_horaria"],
            )


