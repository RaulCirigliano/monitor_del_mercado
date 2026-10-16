from datetime import datetime
import os
import re
from pathlib import Path
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
SHARED_DIRECTIVES_PATH = Path(os.environ.get(
    "TRADING_OLLAMA_PROJECT_DIR",
    Path(__file__).resolve().parents[3] / "trading_ollama",
)) / "guias" / "directivas_cerebro.md"


def _load_shared_directives() -> str:
    try:
        return SHARED_DIRECTIVES_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError("No se pudieron leer las directivas canónicas compartidas.") from exc


class ContrarianEvaluator:
    """
    Evaluador contrarian con razonamiento por etapas:
    1. Tiempo máximo estricto por paso (25-30 segundos).
    2. Obligación de emitir una 'conclusión interna' de pensamiento antes de avanzar.
    3. Progresión desde esa conclusión solo si hay sospecha fundada de asimetría.
    4. Garantía absoluta de entregar una respuesta final estructurada.
    """

    STEP_TIMEOUT = float(getattr(settings, "ollama_timeout", 120.0))

    def __init__(self, use_gemini: bool = False, model: Optional[str] = None):
        self.ollama = OllamaClient(model=model)
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
        shared_system_prompt = f"{_load_shared_directives()}\n\nDIRECTIVA ESPECÍFICA DEL MONITOR:\n{system_prompt}"

        if self.use_gemini:
            if self.gemini.is_available():
                try:
                    return self.gemini.generate_json(shared_system_prompt, user_prompt)
                except Exception as e:
                    logger.warning(
                        "Gemini falló (%s); se intentará Ollama local.",
                        type(e).__name__,
                    )
            else:
                logger.warning(
                    "Gemini fue solicitado pero no está configurado; se intentará Ollama local."
                )

        if not self.ollama.is_available():
            raise RuntimeError(f"Ollama no disponible en {self.ollama.host}")

        return self.ollama.generate_json(
            system_prompt=shared_system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            timeout=call_timeout,
        )

    @staticmethod
    def _compute_atr_levels(snapshot: AssetSnapshot) -> Optional[Dict[str, Any]]:
        """Calcula determinísticamente en Python niveles de entrada, stop loss y take profit basados en ATR(14)."""
        if snapshot is None or snapshot.current_price is None or snapshot.current_price <= 0:
            return None

        price = float(snapshot.current_price)
        currency = snapshot.currency or "USD"
        atr = (
            float(snapshot.atr_14)
            if (snapshot.atr_14 is not None and snapshot.atr_14 > 0)
            else max(price * 0.025, 0.01)
        )

        entry_low = round(max(0.01, price - 0.5 * atr), 2)
        entry_high = round(price, 2)
        entry_mid = (entry_low + entry_high) / 2.0

        stop_price = round(max(0.01, entry_mid - 2.0 * atr), 2)
        if stop_price >= entry_mid:
            stop_price = round(max(0.01, entry_mid * 0.94), 2)

        risk = max(entry_mid - stop_price, 0.01)
        target_price = round(entry_mid + max(6.4 * atr, 3.2 * risk), 2)
        rr_ratio = round((target_price - entry_mid) / risk, 2)

        return {
            "entry_price_range": f"{entry_low:.2f} - {entry_high:.2f} {currency}",
            "stop_loss": f"{stop_price:.2f} {currency}",
            "take_profit": f"{target_price:.2f} {currency}",
            "risk_reward_ratio": rr_ratio,
        }

    def _format_market_context(
        self,
        snapshots_or_snap: Any,
        relevant_tickers: Optional[set] = None,
    ) -> str:
        """Formatea el contexto cuantitativo duro (Z-Score, EMA200, ATR%, RVOL) y niveles deterministas."""
        if isinstance(snapshots_or_snap, AssetSnapshot):
            base = snapshots_or_snap.to_compact_text()
            levels = self._compute_atr_levels(snapshots_or_snap)
            if levels:
                base += (
                    f" | Niveles ATR(14) sugeridos -> Entrada: {levels['entry_price_range']}, "
                    f"Stop Loss (-2x ATR): {levels['stop_loss']}, "
                    f"Target: {levels['take_profit']} (R/B: {levels['risk_reward_ratio']})"
                )
            return base

        if isinstance(snapshots_or_snap, dict):
            benchmarks = {"CL=F", "GC=F", "BTC-USD", "^GSPC", "SPY", "TLT"}
            chunk_snaps = []
            for t, s in snapshots_or_snap.items():
                if not isinstance(s, AssetSnapshot):
                    continue
                if relevant_tickers is None or t in relevant_tickers or t in benchmarks:
                    chunk_snaps.append(self._format_market_context(s))
            return "\n".join(chunk_snaps[:6]) if chunk_snaps else "Sin cotizaciones específicas."

        return "Sin cotizaciones específicas."

    def _step1_diagnose(
        self,
        news_chunk: List[NewsItem],
        snapshots: Dict[str, AssetSnapshot],
        custom_directive: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Paso 1: Emite obligatoriamente una conclusión interna y detecta candidatos o ruido."""
        news_text = "\n\n".join(item.to_compact_text() for item in news_chunk)

        # Contexto de mercado acotado con métricas cuantitativas
        relevant_tickers = set()
        for item in news_chunk:
            for t in item.tickers_detected:
                relevant_tickers.add(t)

        market_text = self._format_market_context(snapshots, relevant_tickers=relevant_tickers)

        prompt = build_step1_prompt(news_text, market_text, custom_directive=custom_directive)

        try:
            result = self._call_llm(
                system_prompt=STEP1_DIAGNOSIS_SYSTEM,
                user_prompt=prompt,
                max_tokens=300,
                timeout=self.STEP_TIMEOUT,
            )
            if not isinstance(result, dict):
                raise ValueError("La respuesta de diagnóstico no es un objeto JSON.")
            conclusion = result.get("conclusion_interna")
            noise_count = result.get("ruido_descartado_count")
            if not isinstance(conclusion, str) or not conclusion.strip():
                raise ValueError("La respuesta de diagnóstico no incluye una conclusión válida.")
            if not isinstance(noise_count, int) or isinstance(noise_count, bool):
                raise ValueError("La respuesta de diagnóstico no incluye un recuento de ruido válido.")
            for candidate_key in ("candidato_oportunidad", "candidato_peligro"):
                candidate = result.get(candidate_key)
                if candidate is not None and not isinstance(candidate, str):
                    raise ValueError(f"El campo {candidate_key} tiene un formato inválido.")
            return result
        except Exception as e:
            logger.warning(
                "No se pudo completar el diagnóstico de IA (%s).",
                type(e).__name__,
            )
            return {
                "conclusion_interna": (
                    f"Evaluación incompleta: no se pudieron clasificar {len(news_chunk)} noticias "
                    "porque el servicio de IA no respondió correctamente."
                ),
                "ruido_descartado_count": 0,
                "candidato_oportunidad": None,
                "candidato_peligro": None,
                "evaluacion_incompleta": True,
            }

    def _step2_build_card(
        self,
        ticker: str,
        prior_conclusion: str,
        snapshot: Optional[AssetSnapshot],
        custom_directive: Optional[str] = None,
        danger: bool = False,
    ) -> Optional[OpportunityCard]:
        """Genera y valida una ficha de oportunidad o alerta de peligro."""
        market_info = self._format_market_context(snapshot) if snapshot else f"Activo: {ticker}"
        prompt_builder = build_step2_danger_prompt if danger else build_step2_opportunity_prompt
        system_prompt = STEP2_DANGER_SYSTEM if danger else STEP2_OPPORTUNITY_SYSTEM
        expected_type = "Trampa de Mercado / Peligro" if danger else "Oportunidad Asimétrica"
        prompt = prompt_builder(ticker, prior_conclusion, market_info, custom_directive=custom_directive)

        try:
            raw_data = self._call_llm(
                system_prompt=system_prompt,
                user_prompt=prompt,
                max_tokens=400,
                timeout=self.STEP_TIMEOUT,
            )
            if not isinstance(raw_data, dict):
                raise ValueError("La ficha devuelta por el LLM no es un diccionario")

            data = dict(raw_data)
            det_levels = self._compute_atr_levels(snapshot) if (snapshot and not danger) else None

            if det_levels:
                if not data.get("nivel_entrada_sugerido"):
                    data["nivel_entrada_sugerido"] = det_levels["entry_price_range"]
                if not data.get("stop_loss_sugerido"):
                    data["stop_loss_sugerido"] = det_levels["stop_loss"]
                if not data.get("target_proyectado"):
                    data["target_proyectado"] = det_levels["take_profit"]
                try:
                    rr_val = float(data.get("ratio_riesgo_beneficio", 0))
                except (TypeError, ValueError):
                    rr_val = 0.0
                if rr_val <= 0:
                    data["ratio_riesgo_beneficio"] = det_levels["risk_reward_ratio"]

            card = OpportunityCard.model_validate(data)
            if card.tipo != expected_type or card.ticker.strip().upper() != ticker.strip().upper():
                raise ValueError("La ficha no coincide con el tipo o ticker solicitado")

            if not danger:
                entry_values = self._extract_prices(card.nivel_entrada_sugerido or "")
                stop_values = self._extract_prices(card.stop_loss_sugerido or "")
                target_values = self._extract_prices(card.target_proyectado or "")

                levels_valid = False
                if entry_values and stop_values and target_values:
                    entry = sum(entry_values[:2]) / min(len(entry_values), 2)
                    stop = stop_values[0]
                    target = target_values[0]
                    if 0 < stop < entry < target:
                        computed_rr = round((target - entry) / (entry - stop), 2)
                        if computed_rr >= settings.min_risk_reward_ratio or det_levels is None:
                            card.ratio_riesgo_beneficio = computed_rr
                            levels_valid = True

                if not levels_valid:
                    if det_levels is not None:
                        card.nivel_entrada_sugerido = det_levels["entry_price_range"]
                        card.stop_loss_sugerido = det_levels["stop_loss"]
                        card.target_proyectado = det_levels["take_profit"]
                        card.ratio_riesgo_beneficio = det_levels["risk_reward_ratio"]
                    else:
                        raise ValueError("Los niveles para una posición larga deben cumplir stop < entrada < objetivo")

            if snapshot is not None:
                card.rsi_14 = snapshot.rsi_14
                card.z_score_20 = snapshot.z_score_20
                card.pct_from_52w_high = snapshot.pct_from_52w_high
                card.ema_200 = snapshot.ema_200
                card.atr_pct = snapshot.atr_pct
                card.rvol_20 = snapshot.rvol_20

            sch = MarketSchedule.check_status(ticker)
            card.horario_mercado = sch.get("horario_argentina")
            card.mercado_abierto = sch.get("mercado_abierto")
            card.proxima_apertura = sch.get("proxima_apertura")
            card.categoria_mercado = sch.get("categoria")
            return card
        except Exception as e:
            logger.warning(
                "No se pudo validar una ficha de IA para %s (%s); se descartó para evitar datos inventados.",
                ticker,
                type(e).__name__,
            )
            return None

    @staticmethod
    def _extract_prices(value: str) -> List[float]:
        """Extrae precios positivos en notación decimal con punto o miles separados por coma."""
        matches = re.findall(r"(?<![\w.])(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?", value)
        prices = []
        for match in matches:
            try:
                price = float(match.replace(",", ""))
            except ValueError:
                continue
            if price > 0:
                prices.append(price)
        return prices

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
        evaluacion_incompleta = False
        seen_opportunity_tickers = set()
        seen_danger_tickers = set()

        # Procesamiento secuencial en micro-lotes con tiempo acotado
        for i in range(0, len(news_items), chunk_size):
            chunk = news_items[i : i + chunk_size]

            # FASE 1: Pensamiento y Conclusión Interna Obligatoria
            diag = self._step1_diagnose(chunk, snapshots, custom_directive=custom_directive)
            if not isinstance(diag, dict):
                diag = {
                    "conclusion_interna": (
                        f"Evaluación incompleta: no se pudieron clasificar {len(chunk)} noticias "
                        "por una respuesta inválida del servicio de IA."
                    ),
                    "ruido_descartado_count": 0,
                    "evaluacion_incompleta": True,
                }
            concl = diag.get("conclusion_interna", "")
            if concl:
                conclusiones_internas.append(concl)
            lote_incompleto = bool(diag.get("evaluacion_incompleta"))
            evaluacion_incompleta = evaluacion_incompleta or lote_incompleto

            try:
                noise_count = int(diag.get("ruido_descartado_count", 0))
            except (TypeError, ValueError):
                noise_count = 0
            total_ruido += max(0, min(len(chunk), noise_count))
            if lote_incompleto:
                continue
            cand_op = diag.get("candidato_oportunidad")
            cand_danger = diag.get("candidato_peligro")

            # FASE 2: Progresión selectiva desde la conclusión previa
            if (
                isinstance(cand_op, str)
                and cand_op.strip()
                and cand_op.strip().upper() != "NULL"
                and cand_op.strip().upper() not in seen_opportunity_tickers
            ):
                cand_ticker = cand_op.strip().upper()
                seen_opportunity_tickers.add(cand_ticker)
                card = self._step2_build_card(
                    cand_ticker, concl, snapshots.get(cand_ticker), custom_directive=custom_directive
                )
                if card and card.ratio_riesgo_beneficio >= settings.min_risk_reward_ratio:
                    valid_opportunities.append(card)

            if (
                isinstance(cand_danger, str)
                and cand_danger.strip()
                and cand_danger.strip().upper() != "NULL"
                and cand_danger.strip().upper() not in seen_danger_tickers
            ):
                danger_ticker = cand_danger.strip().upper()
                seen_danger_tickers.add(danger_ticker)
                card = self._step2_build_card(
                    danger_ticker,
                    concl,
                    snapshots.get(danger_ticker),
                    custom_directive=custom_directive,
                    danger=True,
                )
                if card:
                    valid_dangers.append(card)

        # FASE 3: Síntesis final obligatoria consolidada
        if evaluacion_incompleta:
            sintesis = (
                "Evaluación incompleta: al menos un lote de noticias no pudo ser analizado "
                "por el servicio de IA. Los resultados no representan una clasificación completa."
            )
        elif conclusiones_internas:
            sintesis = " | ".join(conclusiones_internas[:3])
        else:
            sintesis = "No se pudo generar una conclusión de mercado para este ciclo."

        # FASE 4: Hoja de Ruta Práctica para el Operador Novato
        guia_operador = self._build_operator_guide(
            valid_opportunities,
            valid_dangers,
            custom_directive=custom_directive,
            analysis_incomplete=evaluacion_incompleta,
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
        analysis_incomplete: bool = False,
    ) -> GuiaOperador:
        """Construye una hoja de ruta con instrucciones paso a paso y verificación de horarios de mercado en tiempo real."""
        if analysis_incomplete and not opportunities and not dangers:
            sch_general = MarketSchedule.check_status("SPY")
            return GuiaOperador(
                estado_semaforo="ESPERAR / NO OPERAR",
                mensaje_principal=(
                    "La evaluación quedó incompleta porque el servicio de IA no respondió. "
                    "Las noticias no clasificadas no se consideran ruido ni evidencia de ausencia de oportunidades."
                ),
                checklist_pasos=[
                    "No se generó una conclusión de mercado; vuelve a intentar el análisis cuando la IA esté disponible."
                ],
                regla_gestion_riesgo=(
                    "Este resultado no es una señal de mercado. El monitor no envía ni ejecuta órdenes."
                ),
                consejo_psicologico="No tomes decisiones basadas en una evaluación incompleta.",
                horario_mercado=sch_general["horario_argentina"],
                mercado_abierto=sch_general["mercado_abierto"],
                proxima_apertura=sch_general["proxima_apertura"],
                categoria_mercado=sch_general["categoria"],
                recomendacion_horaria=sch_general["recomendacion_horaria"],
            )

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
                    "El horario solo aporta contexto informativo; el monitor no envía ni ejecuta órdenes."
                )
                paso1 = f"1. REFERENCIA DE MERCADO ({sch['estado_texto']}): '{ticker}' ({opp.asset_name}) cotiza en horario de sesión ({sch['horario_argentina']}); este dato es informativo."
            else:
                mensaje_horario = (
                    f"⚠️ ATENCIÓN HORARIO ({sch['estado_texto']}): "
                    f"El mercado físico de {ticker} ({sch['categoria']}) opera de {sch['horario_argentina']}. "
                    f"Actualmente está CERRADO; las cotizaciones pueden estar desactualizadas. "
                    f"Próxima apertura estimada: {sch['proxima_apertura']}. El monitor no transmite ni ejecuta órdenes."
                )
                paso1 = (
                    f"1. CONTEXTO HORARIO ({sch['estado_texto']}): {ticker} cotiza de {sch['horario_argentina']}; "
                    f"próxima apertura estimada: {sch['proxima_apertura']}."
                )

            pasos = [
                paso1,
                f"2. NIVEL DE ENTRADA REFERENCIAL (NO ES UNA ORDEN): {entry}. Ratio riesgo/beneficio estimado: 1 a {opp.ratio_riesgo_beneficio:.1f}.",
                f"3. NIVEL DE INVALIDACIÓN REFERENCIAL (NO ES UNA ORDEN): {stop}. Catalizador de riesgo a monitorear: {opp.catalizador_detonante}.",
                f"4. OBJETIVO REFERENCIAL (NO ES UNA ORDEN): {target}. Soporte secular de fondo: {opp.soporte_secular}.",
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
                f"1. ALERTA INFORMATIVA: '{ticker}' ({danger.asset_name}) fue clasificado con señales de euforia; esto no es una instrucción de compra o venta.",
                "2. Contrasta la señal con datos y fuentes independientes; el análisis automatizado puede ser incorrecto.",
                f"3. HORARIO INFORMATIVO ({sch['estado_texto']}): Este activo cotiza en {sch['horario_argentina']}.",
                "4. Revisa la información y decide de forma independiente; el monitor no transmite ni ejecuta órdenes.",
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
                "1. No se detectaron oportunidades validadas; este análisis no indica comprar, vender ni mantener activos.",
                "2. Revisa las fuentes originales y considera que la cobertura RSS puede ser incompleta.",
                f"3. Horario de referencia de Wall Street: {sch_general['horario_argentina']}.",
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
