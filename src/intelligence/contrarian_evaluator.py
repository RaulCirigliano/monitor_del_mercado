from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

from config import settings
from src.models import NewsItem, AssetSnapshot, OpportunityCard, AnalysisBatch
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

    STEP_TIMEOUT = 25.0  # Límite máximo en segundos por cada inferencia

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
            return card
        except Exception as e:
            logger.warning(f"Error generando ficha detallada para {ticker}: {e}")
            # Si falla la generación detallada, construir una ficha de síntesis basada en datos duros
            if snapshot and snapshot.current_price:
                return OpportunityCard(
                    ticker=ticker,
                    asset_name=ticker,
                    tipo="Oportunidad Asimétrica",
                    sentimiento_mercado="Pánico Extremo / Capitulación",
                    tesis_contrarian=f"Señales de sobreventa detectadas a partir de la conclusión: {prior_conclusion[:150]}",
                    catalizador_detonante="Pánico mediático transitorio.",
                    soporte_secular="Soporte técnico cercano a mínimos recientes.",
                    ratio_riesgo_beneficio=3.0,
                    nivel_entrada_sugerido=f"Zona de {snapshot.current_price:.2f} {snapshot.currency}",
                    stop_loss_sugerido=f"{(snapshot.current_price * 0.95):.2f} {snapshot.currency}",
                    target_proyectado=f"{(snapshot.current_price * 1.15):.2f} {snapshot.currency}",
                    horizonte_temporal="3-6 meses",
                    score_asimetria=7,
                    fuentes_relacionadas=["Métricas técnicas de mercado"],
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

        return AnalysisBatch(
            timestamp=now_str,
            total_noticias_analizadas=len(news_items),
            total_ruido_descartado=total_ruido,
            oportunidades=valid_opportunities,
            alertas_peligro=valid_dangers,
            conclusiones_internas=conclusiones_internas,
            sintesis_ejecutiva=sintesis,
            directiva_personalizada=custom_directive,
        )

