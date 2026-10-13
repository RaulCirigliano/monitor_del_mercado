import pytest
from src.ingestion.deduplicator import Deduplicator
from src.models import OpportunityCard, AnalysisBatch, NewsItem
from src.reporting.markdown_generator import MarkdownReportGenerator
from pathlib import Path
import tempfile


def test_deduplicator():
    dedup = Deduplicator()
    # Test detección de ruido publicitario
    assert dedup.is_noise("Top 10 stocks to buy now for massive gains!") is True
    assert dedup.is_noise("Sponsored post: Best crypto casinos") is True
    assert dedup.is_noise("Federal Reserve maintains interest rates steady") is False

    # Test detección de duplicados
    assert dedup.is_duplicate("Gold plummets 5% on dollar surge", "http://example.com/1") is False
    assert dedup.is_duplicate("Gold plummets 5% on dollar surge", "http://example.com/2") is True


def test_opportunity_card_validation():
    card = OpportunityCard(
        ticker="CL=F",
        asset_name="Crude Oil WTI",
        tipo="Oportunidad Asimétrica",
        sentimiento_mercado="Pánico Extremo / Capitulación",
        tesis_contrarian="La venta masiva por temores de recesión ignora la oferta estructuralmente constreñida.",
        catalizador_detonante="Pánico mediático transitorio.",
        soporte_secular="Inversión insuficiente de capital en exploración y demanda secular sólida.",
        ratio_riesgo_beneficio=3.8,
        nivel_entrada_sugerido="65.00 - 68.00 USD",
        stop_loss_sugerido="60.00 USD",
        target_proyectado="95.00 USD",
        horizonte_temporal="6-12 meses",
        score_asimetria=8,
        fuentes_relacionadas=["Bloomberg Commodities Report"],
    )
    assert card.ratio_riesgo_beneficio == 3.8
    assert card.score_asimetria == 8


def test_markdown_generator():
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = MarkdownReportGenerator(output_dir=Path(tmpdir))
        batch = AnalysisBatch(
            timestamp="2026-10-12 18:00:00",
            total_noticias_analizadas=20,
            total_ruido_descartado=18,
            oportunidades=[
                OpportunityCard(
                    ticker="TLT",
                    asset_name="iShares 20+ Year Treasury Bond ETF",
                    tipo="Oportunidad Asimétrica",
                    sentimiento_mercado="Pánico Extremo / Capitulación",
                    tesis_contrarian="Capitulación histórica en bonos largos por retórica hawkish extrema.",
                    catalizador_detonante="Dato de inflación pico.",
                    soporte_secular="Desaceleración cíclica inevitable y techo de tasas.",
                    ratio_riesgo_beneficio=4.0,
                    nivel_entrada_sugerido="88.00 - 90.00 USD",
                    stop_loss_sugerido="82.00 USD",
                    target_proyectado="115.00 USD",
                    horizonte_temporal="1-2 años",
                    score_asimetria=9,
                    fuentes_relacionadas=["Yield Curve Inversion Coverage"],
                )
            ],
            alertas_peligro=[],
        )

        report_file = gen.generate_report(batch)
        assert report_file.exists()
        content = report_file.read_text(encoding="utf-8")
        assert "Monitor del Mercado" in content
        assert "TLT" in content
        assert "Capitulación histórica" in content


def test_keyword_extraction_and_custom_directive():
    from src.ingestion.rss_collector import RSSCollector

    raw_phrase = "sigue las noticias sobre las recomendaciones que dio maslaton"
    cleaned = RSSCollector._extract_search_keywords(raw_phrase)
    assert "maslaton" in cleaned.lower()
    assert "recomendaciones" in cleaned.lower()
    assert "sigue" not in cleaned.lower()

    # Test de generación de reporte con directiva
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = MarkdownReportGenerator(output_dir=Path(tmpdir))
        batch = AnalysisBatch(
            timestamp="2026-10-12 18:30:00",
            total_noticias_analizadas=5,
            total_ruido_descartado=4,
            oportunidades=[],
            alertas_peligro=[],
            directiva_personalizada="Recomendaciones de Maslatón",
        )
        report_file = gen.generate_report(batch)
        content = report_file.read_text(encoding="utf-8")
        assert "Recomendaciones de Maslatón" in content


def test_guia_operador_and_parsing():
    from src.models import GuiaOperador
    from src.dashboard.report_parser import parse_markdown_report

    guia = GuiaOperador(
        estado_semaforo="OPERAR CON CAUTELA",
        mensaje_principal="Oportunidad detectada en TLT por capitulación de bonos.",
        checklist_pasos=[
            "1. LOCALIZA EL ACTIVO: Busca 'TLT' en tu plataforma.",
            "2. ORDEN DE COMPRA: Configura una orden límite en 78.00 USD.",
            "3. STOP LOSS OBLIGATORIO: Coloca tu orden defensiva en 74.00 USD.",
        ],
        regla_gestion_riesgo="REGLA DEL 1%: Nunca arriesgues más del 1% del total de tu cuenta.",
        consejo_psicologico="Mantén la calma y no operes por impulso.",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        gen = MarkdownReportGenerator(output_dir=Path(tmpdir))
        batch = AnalysisBatch(
            timestamp="2026-10-12 19:00:00",
            total_noticias_analizadas=10,
            total_ruido_descartado=8,
            oportunidades=[],
            alertas_peligro=[],
            guia_operador=guia,
        )
        report_file = gen.generate_report(batch)
        assert report_file.exists()

        parsed = parse_markdown_report(report_file)
        assert "guia_operador" in parsed
        assert parsed["guia_operador"]["estado_semaforo"] == "OPERAR CON CAUTELA"
        assert len(parsed["guia_operador"]["checklist_pasos"]) >= 1


def test_market_schedule_and_operator_guidance():
    from datetime import datetime, timezone, timedelta
    from src.ingestion.market_schedule import MarketSchedule
    from src.intelligence.contrarian_evaluator import ContrarianEvaluator

    arg_tz = timezone(timedelta(hours=-3))

    # 1. Test Crypto (24/7)
    btc_status = MarketSchedule.check_status("BTC-USD")
    assert btc_status["mercado_abierto"] is True
    assert "24/7" in btc_status["estado_texto"]

    # 2. Test TLT con horario simulado de mercado cerrado (20:51 ARG)
    dt_closed = datetime(2026, 10, 12, 20, 51, tzinfo=arg_tz)  # Lunes 20:51 ARG
    tlt_closed = MarketSchedule.check_status("TLT", ref_dt=dt_closed)
    assert tlt_closed["mercado_abierto"] is False
    assert "CERRADO" in tlt_closed["estado_texto"]
    assert "10:30" in tlt_closed["proxima_apertura"]
    assert "datos congelados" in tlt_closed["recomendacion_horaria"] or "cerrado" in tlt_closed["recomendacion_horaria"]

    # 3. Test TLT con horario simulado de mercado abierto (14:00 ARG)
    dt_open = datetime(2026, 10, 12, 14, 0, tzinfo=arg_tz)  # Lunes 14:00 ARG
    tlt_open = MarketSchedule.check_status("TLT", ref_dt=dt_open)
    assert tlt_open["mercado_abierto"] is True
    assert "ABIERTO" in tlt_open["estado_texto"]

    # 4. Test Merval Local (GGAL)
    ggal_status = MarketSchedule.check_status("GGAL")
    assert "Local" in ggal_status["categoria"] or "BYMA" in ggal_status["categoria"]

    # 5. Test integración con ContrarianEvaluator._build_operator_guide
    evaluator = ContrarianEvaluator()
    opp_card = OpportunityCard(
        ticker="TLT",
        asset_name="iShares 20+ Year Treasury Bond ETF",
        tipo="Oportunidad Asimétrica",
        sentimiento_mercado="Pánico Extremo / Capitulación",
        tesis_contrarian="Existe una oportunidad asimétrica favorable en TLT.",
        catalizador_detonante="Tasas altas.",
        soporte_secular="Deuda soberana.",
        ratio_riesgo_beneficio=3.5,
        nivel_entrada_sugerido="78.00 USD",
        stop_loss_sugerido="74.00 USD",
        target_proyectado="95.00 USD",
        horizonte_temporal="6-12 meses",
        score_asimetria=8,
    )
    guia = evaluator._build_operator_guide([opp_card], [])
    assert guia.horario_mercado is not None
    assert "10:30" in guia.horario_mercado
    assert guia.proxima_apertura is not None
    assert len(guia.checklist_pasos) >= 4


def test_no_synthetic_cards_on_llm_failure():
    from unittest.mock import MagicMock
    from src.intelligence.contrarian_evaluator import ContrarianEvaluator
    from src.models import AssetSnapshot

    evaluator = ContrarianEvaluator()
    # Mock OllamaClient para simular fallo/timeout en la llamada al modelo
    evaluator.ollama = MagicMock()
    evaluator.ollama.is_available.return_value = True
    evaluator.ollama.generate_json.side_effect = TimeoutError("Simulated LLM Timeout")

    snapshot = AssetSnapshot(
        ticker="TLT",
        current_price=78.05,
        currency="USD",
        rsi=32.0,
        sma_200=85.0,
        pct_from_52w_high=-18.0,
        pct_from_52w_low=2.0,
    )

    card = evaluator._step2_build_card(
        ticker="TLT",
        prior_conclusion="Conclusión preliminar que falla en generar ficha estructurada",
        snapshot=snapshot,
    )

    # DIRECTIVA ESTRICTA: Ante fallo/timeout del LLM, NO inventar datos, stops fijos ni plantillas
    assert card is None

    # Verificar que ante 0 oportunidades válidas, la guía del operador dicta esperar sin inventar trades
    guia_vacia = evaluator._build_operator_guide([], [])
    assert guia_vacia.estado_semaforo == "ESPERAR / NO OPERAR"
    assert "ruido" in guia_vacia.mensaje_principal.lower()




