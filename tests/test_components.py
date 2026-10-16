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


def _llm_card(ticker="TLT", danger=False):
    return {
        "ticker": ticker,
        "asset_name": "Test asset",
        "tipo": "Trampa de Mercado / Peligro" if danger else "Oportunidad Asimétrica",
        "sentimiento_mercado": (
            "Euforia Desmedida / Techo de Mercado"
            if danger
            else "Pánico Extremo / Capitulación"
        ),
        "tesis_contrarian": "Tesis de prueba",
        "catalizador_detonante": "Catalizador de prueba",
        "soporte_secular": "Soporte de prueba",
        "ratio_riesgo_beneficio": 99 if not danger else 0.5,
        "nivel_entrada_sugerido": "65.00 - 68.00 USD",
        "stop_loss_sugerido": "60.00 USD",
        "target_proyectado": "95.00 USD",
        "horizonte_temporal": "3-6 meses",
        "score_asimetria": 8,
        "fuentes_relacionadas": [],
    }


def test_opportunity_ratio_is_recomputed_from_levels():
    from src.intelligence.contrarian_evaluator import ContrarianEvaluator

    evaluator = ContrarianEvaluator()
    evaluator._call_llm = lambda **kwargs: _llm_card()

    card = evaluator._step2_build_card("TLT", "Conclusión", None)
    assert card is not None
    assert card.ratio_riesgo_beneficio == pytest.approx(4.38, abs=0.01)

    inconsistent = _llm_card()
    inconsistent["stop_loss_sugerido"] = "70.00 USD"
    evaluator._call_llm = lambda **kwargs: inconsistent
    assert evaluator._step2_build_card("TLT", "Conclusión", None) is None


def test_evaluator_generates_danger_alerts():
    from src.intelligence.contrarian_evaluator import ContrarianEvaluator

    evaluator = ContrarianEvaluator()
    evaluator._step1_diagnose = lambda *args, **kwargs: {
        "conclusion_interna": "Euforia excesiva.",
        "ruido_descartado_count": 1,
        "candidato_oportunidad": None,
        "candidato_peligro": "TLT",
    }
    evaluator._call_llm = lambda **kwargs: _llm_card(danger=True)
    news = NewsItem(
        id="one",
        title="Euforia en el mercado de bonos",
        link="https://example.test/news",
        source="Test",
        category="Test",
    )

    batch = evaluator.evaluate([news], {})
    assert len(batch.alertas_peligro) == 1
    assert batch.alertas_peligro[0].tipo == "Trampa de Mercado / Peligro"
    assert batch.total_ruido_descartado == 1


def test_report_parser_includes_danger_cards():
    from src.dashboard.report_parser import parse_markdown_report
    from src.models import GuiaOperador

    danger = OpportunityCard(
        **_llm_card(danger=True),
    )
    batch = AnalysisBatch(
        timestamp="2026-10-12 18:00:00",
        total_noticias_analizadas=1,
        total_ruido_descartado=0,
        alertas_peligro=[danger],
        guia_operador=GuiaOperador(
            estado_semaforo="ALERTA DE PELIGRO",
            mensaje_principal="No entrar por euforia.",
            regla_gestion_riesgo="Preservar capital.",
            consejo_psicologico="Evitar FOMO.",
        ),
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        report = MarkdownReportGenerator(output_dir=Path(tmpdir)).generate_report(batch)
        parsed = parse_markdown_report(report)
    assert parsed["oportunidades"] == []
    assert len(parsed["alertas_peligro"]) == 1
    assert parsed["alertas_peligro"][0]["ticker"] == "TLT"


def test_report_path_resolution_rejects_traversal(tmp_path, monkeypatch):
    from config import settings
    from src.dashboard.server import DashboardRequestHandler

    root = tmp_path / "reportes"
    root.mkdir()
    (root / "valid.md").write_text("ok", encoding="utf-8")
    (tmp_path / "outside.md").write_text("secret", encoding="utf-8")
    monkeypatch.setattr(settings, "reports_dir", root)

    assert DashboardRequestHandler._resolve_report_path("valid.md") == (root / "valid.md").resolve()
    assert DashboardRequestHandler._resolve_report_path("../outside.md") is None


def test_dashboard_rejects_cross_origin_requests():
    from email.message import Message
    from src.dashboard.server import DashboardRequestHandler

    handler = object.__new__(DashboardRequestHandler)
    handler.headers = Message()
    handler.headers["Host"] = "127.0.0.1:8520"
    handler.headers["Origin"] = "http://127.0.0.1:8520"
    assert handler._is_local_request() is True

    handler.headers.replace_header("Origin", "http://attacker.test")
    assert handler._is_local_request() is False


def test_market_schedule_tracks_dst_and_nyse_holidays():
    from datetime import datetime, timezone, timedelta
    from src.ingestion.market_schedule import MarketSchedule

    arg_tz = timezone(timedelta(hours=-3))
    winter = MarketSchedule.check_status(
        "SPY", ref_dt=datetime(2026, 1, 12, 10, 45, tzinfo=arg_tz)
    )
    summer = MarketSchedule.check_status(
        "SPY", ref_dt=datetime(2026, 7, 13, 10, 45, tzinfo=arg_tz)
    )
    thanksgiving = MarketSchedule.check_status(
        "SPY", ref_dt=datetime(2026, 11, 26, 13, 0, tzinfo=arg_tz)
    )
    early_close = MarketSchedule.check_status(
        "SPY", ref_dt=datetime(2026, 11, 27, 16, 0, tzinfo=arg_tz)
    )

    assert winter["mercado_abierto"] is False
    assert "11:30" in winter["proxima_apertura"]
    assert summer["mercado_abierto"] is True
    assert thanksgiving["mercado_abierto"] is False
    assert "viernes" in thanksgiving["proxima_apertura"].lower()
    assert early_close["mercado_abierto"] is False


def test_dashboard_port_selection_skips_in_use_ports():
    import socket
    from src.dashboard.server import find_free_port

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        start_port = occupied.getsockname()[1]
        selected_port = find_free_port(start_port, max_attempts=3)
        assert start_port < selected_port < start_port + 3


def test_rsi_uses_wilder_smoothing_and_handles_flat_prices():
    import pandas as pd
    from src.ingestion.market_data import MarketDataFetcher

    fetcher = MarketDataFetcher()
    flat = pd.Series([10.0] * 20)
    rising = pd.Series([float(value) for value in range(20)])
    assert fetcher._calculate_rsi(flat) == 50.0
    assert fetcher._calculate_rsi(rising) == 100.0


def test_pipeline_saves_empty_scan_report_and_preserves_ticker_order(tmp_path):
    from src.pipeline import MarketMonitorPipeline

    pipeline = MarketMonitorPipeline()
    pipeline.collector.collect_all = lambda **kwargs: []
    pipeline.report_generator = MarkdownReportGenerator(output_dir=tmp_path)
    batch = pipeline.run()

    assert batch.total_noticias_analizadas == 0
    assert list(tmp_path.rglob("*.md"))

    items = [
        NewsItem(
            id=f"id{index}",
            title=f"News item number {index}",
            link=f"https://example.test/{index}",
            source="Test",
            category="Test",
            tickers_detected=["NVDA", "AAPL"] if index == 0 else ["MSFT"],
        )
        for index in range(2)
    ]
    assert MarketMonitorPipeline._ordered_tickers(items)[:3] == ["NVDA", "AAPL", "MSFT"]


def test_ollama_invalid_http_json_raises_a_clear_value_error(monkeypatch):
    import json
    from unittest.mock import MagicMock
    from src.intelligence import ollama_client

    response = MagicMock()
    response.json.side_effect = json.JSONDecodeError("invalid", "", 0)
    client_context = MagicMock()
    client_context.__enter__.return_value.post.return_value = response
    monkeypatch.setattr(ollama_client.httpx, "Client", lambda **kwargs: client_context)

    client = ollama_client.OllamaClient(host="http://ollama.test")
    with pytest.raises(ValueError, match="JSON incompleto o inválido"):
        client.generate_json("system", "user")


def test_ollama_model_health_requires_the_configured_model(monkeypatch):
    import httpx
    from src.intelligence import ollama_client

    models_response = {"models": [{"name": "another-model:latest"}]}
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=models_response, request=request)
    )
    real_client = httpx.Client
    monkeypatch.setattr(
        ollama_client.httpx,
        "Client",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )

    client = ollama_client.OllamaClient(
        host="http://ollama.test", model="qwen2.5:3b"
    )
    assert client.is_available()
    assert not client.is_model_available()


def test_failed_llm_diagnosis_does_not_report_unclassified_news_as_noise():
    from src.intelligence.contrarian_evaluator import ContrarianEvaluator

    news = NewsItem(
        id="one",
        title="A sufficiently long test headline",
        link="https://example.test/news",
        source="Test",
        category="Test",
    )
    evaluator = ContrarianEvaluator()
    evaluator._call_llm = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("offline"))

    diagnosis = evaluator._step1_diagnose([news], {})
    assert diagnosis["evaluacion_incompleta"] is True
    assert diagnosis["ruido_descartado_count"] == 0

    batch = evaluator.evaluate([news], {})
    assert batch.total_ruido_descartado == 0
    assert "incompleta" in batch.sintesis_ejecutiva.lower()
    assert "no se consideran ruido" in batch.guia_operador.mensaje_principal.lower()


def test_malformed_llm_diagnosis_is_reported_as_incomplete():
    from src.intelligence.contrarian_evaluator import ContrarianEvaluator

    evaluator = ContrarianEvaluator()
    evaluator._call_llm = lambda **kwargs: {}
    news = NewsItem(
        id="one",
        title="A sufficiently long test headline",
        link="https://example.test/news",
        source="Test",
        category="Test",
    )

    diagnosis = evaluator._step1_diagnose([news], {})
    assert diagnosis["evaluacion_incompleta"] is True
    assert diagnosis["ruido_descartado_count"] == 0


def test_report_parser_does_not_fill_missing_card_data_with_defaults(tmp_path):
    from src.dashboard.report_parser import parse_markdown_report

    report = tmp_path / "partial.md"
    report.write_text(
        "## 🎯 1. Fichas de Oportunidad Asimétrica\n"
        "### 📌 TEST — Test Asset\n"
        "* **Clasificación:** `Oportunidad Asimétrica`\n",
        encoding="utf-8",
    )

    card = parse_markdown_report(report)["oportunidades"][0]
    assert card["sentimiento_mercado"] is None
    assert card["score_asimetria"] is None
    assert card["ratio_riesgo_beneficio"] is None
    assert card["nivel_entrada_sugerido"] is None
    assert card["tesis_contrarian"] is None


def test_report_generator_does_not_overwrite_same_timestamp_reports(tmp_path, monkeypatch):
    from datetime import datetime as RealDateTime
    from src.reporting import markdown_generator

    class FrozenDateTime:
        @classmethod
        def now(cls):
            return RealDateTime(2026, 10, 14, 12, 34, 56, 123456)

    monkeypatch.setattr(markdown_generator, "datetime", FrozenDateTime)
    generator = MarkdownReportGenerator(output_dir=tmp_path)
    batch = AnalysisBatch(
        timestamp="2026-10-14 12:34:56",
        total_noticias_analizadas=0,
        total_ruido_descartado=0,
    )

    first = generator.generate_report(batch)
    second = generator.generate_report(batch)
    assert first != second
    assert first.exists()
    assert second.exists()


def test_dashboard_auto_injection_is_disabled_by_default():
    html = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(
        encoding="utf-8"
    )
    checkbox = html.split('id="radar-autoinject"', 1)[1].split(">", 1)[0]
    assert "checked" not in checkbox


def test_monitor_proxy_forwards_shared_brain_token_and_selection(monkeypatch):
    import json
    from src.dashboard import server

    captured = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"engine":"ollama","model":"deepseek-r1:8b"}'

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["token"] = request.get_header("X-api-token")
        captured["method"] = request.get_method()
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("TRADING_OLLAMA_API_TOKEN", "local-test-token")
    monkeypatch.setattr(server, "urlopen", fake_urlopen)

    status, payload = server.DashboardRequestHandler._request_trading_brain(
        "/api/system/brain",
        method="POST",
        payload={"engine": "ollama", "model": "deepseek-r1:8b"},
    )

    assert status == 200
    assert payload == {"engine": "ollama", "model": "deepseek-r1:8b"}
    assert captured == {
        "url": "http://127.0.0.1:18767/api/system/brain",
        "token": "local-test-token",
        "method": "POST",
        "body": {"engine": "ollama", "model": "deepseek-r1:8b"},
        "timeout": 4,
    }


def test_pipeline_uses_selected_ollama_model():
    from src.pipeline import MarketMonitorPipeline

    pipeline = MarketMonitorPipeline(model="deepseek-r1:8b")

    assert pipeline.evaluator.ollama.model == "deepseek-r1:8b"


def test_commodity_schedule_respects_sunday_opening_and_friday_close():
    from datetime import datetime, timezone, timedelta
    from src.ingestion.market_schedule import MarketSchedule

    arg_tz = timezone(timedelta(hours=-3))
    before_sunday_open = MarketSchedule.check_status(
        "CL=F", ref_dt=datetime(2026, 10, 11, 18, 59, tzinfo=arg_tz)
    )
    sunday_open = MarketSchedule.check_status(
        "CL=F", ref_dt=datetime(2026, 10, 11, 19, 0, tzinfo=arg_tz)
    )
    weekday_late = MarketSchedule.check_status(
        "CL=F", ref_dt=datetime(2026, 10, 13, 23, 0, tzinfo=arg_tz)
    )
    friday_close = MarketSchedule.check_status(
        "CL=F", ref_dt=datetime(2026, 10, 16, 18, 0, tzinfo=arg_tz)
    )

    assert before_sunday_open["mercado_abierto"] is False
    assert sunday_open["mercado_abierto"] is True
    assert weekday_late["mercado_abierto"] is True
    assert friday_close["mercado_abierto"] is False


def test_market_snapshot_does_not_invent_52_week_extremes(monkeypatch):
    from types import SimpleNamespace
    import pandas as pd
    from src.ingestion import market_data

    history = pd.DataFrame({"Close": [10.0, 11.0, 12.0]})
    quote = SimpleNamespace(
        history=lambda **kwargs: history,
        fast_info=SimpleNamespace(
            year_high=float("nan"),
            year_low=None,
            currency="USD",
            last_price=float("nan"),
            previous_close=0,
        ),
    )
    monkeypatch.setattr(market_data.yf, "Ticker", lambda ticker: quote)

    snapshot = market_data.MarketDataFetcher().get_snapshot("TEST")
    assert snapshot is not None
    assert snapshot.current_price == 12
    assert snapshot.change_pct_24h == pytest.approx(9.09, abs=0.01)
    assert snapshot.fifty_two_week_high is None
    assert snapshot.fifty_two_week_low is None
    assert snapshot.pct_from_52w_high is None
    assert snapshot.pct_from_52w_low is None


def test_rss_http_failure_is_logged_and_returns_no_items(monkeypatch, caplog):
    import httpx
    from src.ingestion import rss_collector

    real_client = httpx.Client
    transport = httpx.MockTransport(
        lambda request: httpx.Response(503, request=request)
    )
    monkeypatch.setattr(
        rss_collector.httpx,
        "Client",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )

    items = rss_collector.RSSCollector().fetch_feed(
        "https://feeds.example.test/rss", "Test feed", "Test"
    )
    assert items == []
    assert "respondió con HTTP 503" in caplog.text


def test_dashboard_returns_404_without_reports_and_400_for_invalid_json(
    tmp_path, monkeypatch
):
    from http.server import HTTPServer
    from threading import Thread
    import httpx
    from config import settings
    from src.dashboard.server import DashboardRequestHandler

    reports_dir = tmp_path / "reportes"
    reports_dir.mkdir()
    monkeypatch.setattr(settings, "reports_dir", reports_dir)

    server = HTTPServer(("127.0.0.1", 0), DashboardRequestHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        with httpx.Client() as client:
            missing = client.get(f"{base_url}/api/reports/latest")
            invalid = client.post(
                f"{base_url}/api/scan",
                content="{",
                headers={"Content-Type": "application/json"},
            )
        assert missing.status_code == 404
        assert "No hay reportes disponibles" in missing.json()["error"]
        assert invalid.status_code == 400
        assert "JSON válido" in invalid.json()["error"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_new_tickers_and_bilingual_keywords_detection():
    from src.ingestion.rss_collector import RSSCollector

    collector = RSSCollector()

    # Acciones US/Global y ETFs China/IA
    tech_text = (
        "Nvidia unveils Blackwell architecture while Apple iPhone sales in Cupertino "
        "compete with Tesla Cybertruck, Microsoft Copilot on Azure, and Alibaba AliExpress. "
        "Investors watch SPDR S&P, MSCI China, China Internet Krane ETF, and Robotics Artificial Intelligence ETF."
    )
    detected_tech = collector._extract_tickers(tech_text)
    for expected in ["NVDA", "AAPL", "TSLA", "MSFT", "BABA", "SPY", "MCHI", "KWEB", "BOTZ"]:
        assert expected in detected_tech, f"Falta {expected} en {detected_tech}"

    # Acciones Argentinas (BYMA .BA)
    byma_text = (
        "Fuerte volumen en YPF por Vaca Muerta, junto a Grupo Financiero Galicia, "
        "Pampa Energía, Banco Macro, Aluar y Ternium en la bolsa porteña."
    )
    detected_byma = collector._extract_tickers(byma_text)
    for expected_ba in ["YPFD.BA", "GGAL.BA", "PAMP.BA", "BMA.BA", "ALUA.BA", "TXAR.BA"]:
        assert expected_ba in detected_byma, f"Falta {expected_ba} en {detected_byma}"

    # Extracción bilingüe de palabras clave
    en_query = "Follow the latest news about Nvidia and semiconductor tariffs"
    cleaned_en = RSSCollector._extract_search_keywords(en_query)
    assert "nvidia" in cleaned_en.lower()
    assert "follow" not in cleaned_en.lower()


def test_market_data_fetcher_quantitative_metrics_and_ttl(monkeypatch):
    from types import SimpleNamespace
    import numpy as np
    import pandas as pd
    from src.ingestion import market_data

    n = 220
    closes = pd.Series(np.linspace(100.0, 80.0, n))
    # Añadir caída abrupta al final para probar Z-Score negativo y RVOL alto
    closes.iloc[-1] = 72.0
    highs = closes + 2.0
    lows = closes - 2.0
    volumes = pd.Series([1_000_000.0] * (n - 1) + [2_500_000.0])

    history = pd.DataFrame({
        "High": highs,
        "Low": lows,
        "Close": closes,
        "Volume": volumes,
    })

    call_count = {"count": 0}

    def fake_ticker(symbol):
        call_count["count"] += 1
        return SimpleNamespace(
            history=lambda **kwargs: history,
            fast_info=SimpleNamespace(
                year_high=105.0,
                year_low=70.0,
                currency="USD",
                last_price=72.0,
                previous_close=80.0,
            ),
        )

    monkeypatch.setattr(market_data.yf, "Ticker", fake_ticker)

    fetcher = market_data.MarketDataFetcher(cache_ttl=300.0)
    snap = fetcher.get_snapshot("NVDA")
    assert snap is not None
    assert snap.sma_50 is not None and snap.sma_50 > 0
    assert snap.ema_200 is not None and snap.ema_200 > 0
    assert snap.z_score_20 is not None and snap.z_score_20 < -1.5
    assert snap.atr_14 == pytest.approx(4.0, abs=0.5)
    assert snap.atr_pct is not None and snap.atr_pct > 0
    assert snap.rvol_20 is not None and snap.rvol_20 > 2.0
    assert call_count["count"] == 1

    # Segunda llamada dentro del TTL usa caché
    snap_cached = fetcher.get_snapshot("NVDA")
    assert snap_cached is snap
    assert call_count["count"] == 1

    # Expirar TTL y verificar recarga
    fetcher._cache_timestamps["NVDA"] -= 301.0
    snap_refreshed = fetcher.get_snapshot("NVDA")
    assert snap_refreshed is not None
    assert call_count["count"] == 2


def test_deterministic_atr_levels_and_market_context():
    from src.intelligence.contrarian_evaluator import ContrarianEvaluator
    from src.models import AssetSnapshot

    evaluator = ContrarianEvaluator()
    snap = AssetSnapshot(
        ticker="YPFD.BA",
        name="YPF S.A.",
        current_price=100.0,
        currency="ARS",
        change_pct_24h=-6.5,
        pct_from_52w_high=-25.0,
        pct_from_52w_low=12.0,
        rsi_14=24.5,
        sma_50=112.0,
        ema_200=95.0,
        z_score_20=-2.45,
        atr_14=5.0,
        atr_pct=5.0,
        rvol_20=2.3,
    )

    ctx = evaluator._format_market_context(snap)
    assert "Z-Score(20): -2.45" in ctx
    assert "EMA(200): 95.00" in ctx
    assert "ATR(14): 5.00 (5.00%)" in ctx
    assert "RVOL(20): 2.30x" in ctx

    # Simular que el LLM devuelve niveles incoherentes (stop > entrada) pero existe AssetSnapshot real
    bad_llm_card = _llm_card(ticker="YPFD.BA")
    bad_llm_card["nivel_entrada_sugerido"] = ""
    bad_llm_card["stop_loss_sugerido"] = "150.00 ARS"
    bad_llm_card["target_proyectado"] = "80.00 ARS"
    evaluator._call_llm = lambda **kwargs: bad_llm_card

    card = evaluator._step2_build_card("YPFD.BA", "Capitulación en Vaca Muerta", snap)
    assert card is not None
    assert card.risk_reward_ratio >= 3.0
    assert "ARS" in card.entry_price_range
    assert "ARS" in card.stop_loss
    assert "ARS" in card.take_profit
    assert card.z_score_20 == -2.45
    assert card.ema_200 == 95.0
    assert card.atr_pct == 5.0


def test_inject_endpoint_sends_x_api_token_header(monkeypatch):
    from http.server import HTTPServer
    from threading import Thread
    import urllib.request
    import httpx
    from src.dashboard.server import DashboardRequestHandler

    captured_requests = []

    class DummyResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return b'{"status":"injected","ok":true}'

    def fake_urlopen(req, timeout=4):
        captured_requests.append(req)
        return DummyResponse()

    monkeypatch.setenv("TRADING_OLLAMA_API_TOKEN", "secret-argon-token-999")
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    server = HTTPServer(("127.0.0.1", 0), DashboardRequestHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        payload = {
            "asset": "YPFD.BA",
            "text": "[RSI: 24.5 | Z-Score: -2.45 | % vs 52w High: -25.0%] Tesis Contrarian: Capitulación en energía.",
            "confidence": 85,
            "type": "Oportunidad",
        }
        with httpx.Client() as client:
            res = client.post(
                f"{base_url}/api/inject_to_trading_bot",
                json=payload,
                headers={"Host": f"127.0.0.1:{server.server_port}"},
            )
        assert res.status_code == 200
        assert len(captured_requests) == 1
        sent_req = captured_requests[0]
        assert sent_req.get_header("X-api-token") == "secret-argon-token-999"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_pipeline_collect_candidates(monkeypatch):
    from src.pipeline import MarketMonitorPipeline
    from src.models import NewsItem, AssetSnapshot

    pipeline = MarketMonitorPipeline()

    fake_news = [
        NewsItem(
            id="hash-1",
            title="Capitulación en Bonos del Tesoro",
            link="https://example.com/tlt",
            source="Yahoo Finance",
            category="macro_and_markets",
            tickers_detected=["TLT"],
        )
    ]
    monkeypatch.setattr(pipeline.collector, "collect_all", lambda **kw: fake_news)
    fake_snap = AssetSnapshot(
        ticker="TLT",
        current_price=88.50,
        currency="USD",
        change_pct_24h=-1.5,
        rsi_14=27.5,
        z_score_20=-2.3,
        ema_200=92.0,
        atr_14=1.2,
        atr_pct=1.35,
        rvol_20=1.6,
    )
    monkeypatch.setattr(pipeline.market_fetcher, "get_snapshot", lambda ticker: fake_snap if ticker == "TLT" else None)

    candidates = pipeline.collect_candidates(category_filter="macro_and_markets", custom_directive="bonos", limit_tickers=5)

    assert candidates["news_count"] == 1
    assert "TLT" in candidates["tickers"]
    assert "TLT" in candidates["snapshots"]
    snap_tlt = candidates["snapshots"]["TLT"]
    assert snap_tlt["rsi_14"] == 27.5
    assert snap_tlt["z_score_20"] == -2.3
    assert "schedule" in snap_tlt


def test_cio_candidates_endpoint(monkeypatch):
    from http.server import HTTPServer
    from threading import Thread
    import httpx
    from src.dashboard.server import DashboardRequestHandler
    from src.pipeline import MarketMonitorPipeline

    fake_candidates = {
        "timestamp": "2026-10-15T20:00:00",
        "news_count": 2,
        "tickers": ["TLT", "CL=F"],
        "snapshots": {"TLT": {"current_price": 88.5, "rsi_14": 26.0}},
    }
    monkeypatch.setattr(MarketMonitorPipeline, "collect_candidates", lambda self, **kw: fake_candidates)

    server = HTTPServer(("127.0.0.1", 0), DashboardRequestHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        with httpx.Client() as client:
            res = client.get(
                f"{base_url}/api/cio/candidates?category=macro_and_markets",
                headers={"Host": f"127.0.0.1:{server.server_port}"},
            )
        assert res.status_code == 200
        data = res.json()
        assert data["news_count"] == 2
        assert "TLT" in data["tickers"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_cio_publish_endpoint_and_auto_inject(monkeypatch, tmp_path):
    import json
    from http.server import HTTPServer
    from threading import Thread
    import httpx
    import urllib.request
    from config import settings
    from src.dashboard.server import DashboardRequestHandler

    monkeypatch.setattr(settings, "reports_dir", tmp_path)

    captured_injections = []

    class DummyResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return b'{"status":"ok","injected":true}'

    def fake_urlopen(req, timeout=4):
        captured_injections.append(req)
        return DummyResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    server = HTTPServer(("127.0.0.1", 0), DashboardRequestHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        payload = {
            "motor_evaluador": "Antigravity CIO",
            "sintesis_ejecutiva": "Tesis institucional CIO sobre TLT",
            "conclusiones_internas": ["Sobreventa extrema", "Asimetría 1:3.5"],
            "oportunidades": [
                {
                    "ticker": "TLT",
                    "asset_name": "iShares 20+ Year Treasury Bond ETF",
                    "tipo": "Oportunidad Asimétrica",
                    "sentimiento_mercado": "Pánico Extremo / Capitulación",
                    "tesis_contrarian": "Capitulación en bonos soberanos",
                    "catalizador_detonante": "Subastas absorbidas",
                    "soporte_secular": "Refugio macro en desaceleración",
                    "ratio_riesgo_beneficio": 3.5,
                    "nivel_entrada_sugerido": "88.00 - 88.50 USD",
                    "stop_loss_sugerido": "85.00 USD",
                    "target_proyectado": "99.00 USD",
                    "horizonte_temporal": "3-6 meses",
                    "score_asimetria": 9,
                    "rsi_14": 25.5,
                    "z_score_20": -2.4,
                }
            ],
            "alertas_peligro": [],
            "auto_inject": True,
        }
        with httpx.Client() as client:
            res = client.post(
                f"{base_url}/api/cio/publish",
                json=payload,
                headers={"Host": f"127.0.0.1:{server.server_port}"},
            )
        assert res.status_code == 200
        res_data = res.json()
        assert res_data["success"] is True
        assert "report_path" in res_data
        assert res_data["injection"] is not None
        assert res_data["injection"]["status_code"] == 200

        # Verificar reporte generado en disco
        saved_file = Path(res_data["report_path"])
        assert saved_file.exists()
        content = saved_file.read_text(encoding="utf-8")
        assert "Antigravity CIO" in content
        assert "TLT" in content

        # Verificar payload de inyección enviado
        assert len(captured_injections) == 1
        req_sent = captured_injections[0]
        sent_body = json.loads(req_sent.data.decode("utf-8"))
        assert sent_body["asset"] == "TLT"
        assert sent_body["source"] == "Antigravity CIO"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_report_parser_motor_evaluador(tmp_path):
    from src.dashboard.report_parser import parse_markdown_report

    cio_md = tmp_path / "RADAR_CIO_test.md"
    cio_md.write_text(
        "# 🦅 Monitor del Mercado — Reporte de Inteligencia Contrarian\n"
        "**Modo de Escaneo:** `🛰️ RADAR AUTÓNOMO`  \n"
        "**Motor Evaluador:** `Antigravity CIO`  \n"
        "**Fecha de Emisión:** 2026-10-15 22:00:00  \n"
        "> **Veredicto Ejecutivo:** Análisis CIO.\n",
        encoding="utf-8",
    )
    parsed = parse_markdown_report(cio_md)
    assert parsed["motor_evaluador"] == "Antigravity CIO"

    ollama_md = tmp_path / "RADAR_ollama_test.md"
    ollama_md.write_text(
        "# 🦅 Monitor del Mercado — Reporte de Inteligencia Contrarian\n"
        "**Modo de Escaneo:** `🛰️ RADAR AUTÓNOMO`  \n"
        "**Motor Evaluador:** `Ollama Local`  \n"
        "**Fecha de Emisión:** 2026-10-15 22:00:00  \n"
        "> **Veredicto Ejecutivo:** Análisis Ollama.\n",
        encoding="utf-8",
    )
    parsed_ollama = parse_markdown_report(ollama_md)
    assert parsed_ollama["motor_evaluador"] == "Ollama Local"

