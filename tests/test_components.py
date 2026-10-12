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
