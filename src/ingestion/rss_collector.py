import hashlib
import logging
import re
from typing import Dict, List, Optional
import feedparser
import httpx
from bs4 import BeautifulSoup

from config import settings
from src.models import NewsItem
from src.ingestion.deduplicator import Deduplicator

logger = logging.getLogger(__name__)


class RSSCollector:
    """Colector y normalizador de fuentes RSS para ingesta rápida de bajo consumo."""

    # Mapeo de términos de materias primas, índices, acciones globales, China/IA y Argentina (BYMA) a tickers de yfinance
    KEYWORD_TICKER_MAP = {
        # Criptoactivos
        r"\b(bitcoin|btc)\b": "BTC-USD",
        r"\b(ethereum|ether|eth)\b": "ETH-USD",
        r"\b(solana|sol)\b": "SOL-USD",
        # Materias Primas y Energía
        r"\b(crude oil|petr[oó]leo|wti|brent)\b": "CL=F",
        r"\b(gold|oro)\b": "GC=F",
        r"\b(silver|plata)\b": "SI=F",
        r"\b(natural gas|gas natural)\b": "NG=F",
        # Bonos e Índices Macro
        r"\b(sp500|s&p 500|s&p500)\b": "^GSPC",
        r"\b(spdr s&p|spy|s&p 500 etf)\b": "SPY",
        r"\b(nasdaq|qqq)\b": "QQQ",
        r"\b(treasury yields?|bonos del tesoro|tlt|10-year yield)\b": "TLT",
        r"\b(dxy|dollar index|d[oó]lar)\b": "DX-Y.NYB",
        # Acciones US / Globales
        r"\b(nvidia|nvda|blackwell|geforce)\b": "NVDA",
        r"\b(apple|aapl|iphone|cupertino)\b": "AAPL",
        r"\b(tesla|tsla|elon musk|cybertruck)\b": "TSLA",
        r"\b(microsoft|msft|azure|copilot)\b": "MSFT",
        r"\b(alibaba|baba|jack ma|aliexpress)\b": "BABA",
        # ETFs China / IA / Robótica
        r"\b(msci china|mchi)\b": "MCHI",
        r"\b(china internet|kweb|krane|china tech)\b": "KWEB",
        r"\b(robotics|botz|artificial intelligence etf|rob[oó]tica)\b": "BOTZ",
        # Argentina (BYMA / Merval)
        r"\b(ypf|ypfd|vaca muerta)\b": "YPFD.BA",
        r"\b(grupo financiero galicia|banco galicia|galicia|ggal)\b": "GGAL.BA",
        r"\b(pampa energ[ií]a|pamp)\b": "PAMP.BA",
        r"\b(banco macro|bma)\b": "BMA.BA",
        r"\b(aluar|alua)\b": "ALUA.BA",
        r"\b(ternium|txar)\b": "TXAR.BA",
    }

    BYMA_ALIAS_MAP = {
        "GGAL": "GGAL.BA",
        "YPFD": "YPFD.BA",
        "YPF": "YPFD.BA",
        "PAMP": "PAMP.BA",
        "BMA": "BMA.BA",
        "ALUA": "ALUA.BA",
        "TXAR": "TXAR.BA",
    }

    def __init__(self, deduplicator: Optional[Deduplicator] = None):
        self.deduplicator = deduplicator or Deduplicator()
        self.client_headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        }

    def _clean_html(self, raw_html: str) -> str:
        """Limpia etiquetas HTML y entidades devolviendo texto plano legible."""
        if not raw_html:
            return ""
        soup = BeautifulSoup(raw_html, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        return re.sub(r"\s+", " ", text).strip()

    def _extract_tickers(self, text: str) -> List[str]:
        """Extrae tickers explícitos ($TICKER o TICKER en mayúsculas) y por palabras clave."""
        found = set()

        # 1. Tickers con signo de dólar: $AAPL, $TSLA, $GGAL.BA, etc.
        dollar_tickers = re.findall(r"\$([A-Z]{1,6}(?:\.BA)?)\b", text)
        for t in dollar_tickers:
            found.add(self.BYMA_ALIAS_MAP.get(t, t))

        # 2. Tickers entre paréntesis: (NYSE: BABA), (NASDAQ: MSFT), (BYMA: GGAL), (NVDA)
        paren_tickers = re.findall(r"\((?:[A-Z]+:\s*)?([A-Z]{2,6}(?:\.BA)?)\)", text)
        for t in paren_tickers:
            if t not in {"CEO", "CFO", "IPO", "FED", "SEC", "ETF", "GDP", "CPI", "USA", "USD", "BYMA", "BCRA"}:
                found.add(self.BYMA_ALIAS_MAP.get(t, t))

        # 3. Mapeo semántico bilingüe de commodities, macro, tech y acciones argentinas
        lower_text = text.lower()
        for pattern, symbol in self.KEYWORD_TICKER_MAP.items():
            if re.search(pattern, lower_text):
                found.add(symbol)

        return sorted(list(found))

    def fetch_feed(self, url: str, source_name: str, category_name: str) -> List[NewsItem]:
        """Descarga e interpreta un feed RSS individual."""
        items: List[NewsItem] = []
        try:
            with httpx.Client(headers=self.client_headers, timeout=15.0, follow_redirects=True) as client:
                response = client.get(url)
                if response.status_code != 200:
                    logger.warning(
                        "El feed %s respondió con HTTP %s",
                        source_name,
                        response.status_code,
                    )
                    return items
                content = response.text
        except Exception as exc:
            logger.warning(
                "No se pudo descargar el feed %s (%s).",
                source_name,
                type(exc).__name__,
            )
            return items

        try:
            feed = feedparser.parse(content)
        except Exception as exc:
            logger.warning(
                "No se pudo interpretar el feed %s (%s).",
                source_name,
                type(exc).__name__,
            )
            return items

        if getattr(feed, "bozo", False):
            logger.warning("El feed %s contiene XML mal formado.", source_name)

        if not hasattr(feed, "entries") or not feed.entries:
            return items

        for entry in feed.entries[: settings.max_items_per_feed]:
            title_raw = getattr(entry, "title", "")
            link_raw = getattr(entry, "link", "")
            summary_raw = getattr(entry, "summary", getattr(entry, "description", ""))
            published_raw = getattr(entry, "published", getattr(entry, "updated", None))
            title = self._clean_html(title_raw if isinstance(title_raw, str) else "")
            link = link_raw.strip() if isinstance(link_raw, str) else ""
            summary = self._clean_html(summary_raw if isinstance(summary_raw, str) else "")
            published = published_raw if isinstance(published_raw, str) else None

            if not title or len(title) < 10:
                continue

            # Filtro de ruido publicitario
            if self.deduplicator.is_noise(title, summary):
                continue

            # Filtro de duplicados
            if self.deduplicator.is_duplicate(title, link):
                continue

            # Generar hash identificador
            item_id = hashlib.sha256(f"{title}|{link}".encode("utf-8")).hexdigest()[:16]

            # Detectar menciones de activos/tickers
            combined_text = f"{title}. {summary}"
            tickers = self._extract_tickers(combined_text)

            try:
                items.append(NewsItem(
                    id=item_id,
                    title=title,
                    link=link,
                    source=source_name,
                    category=category_name,
                    published=published,
                    summary=summary,
                    tickers_detected=tickers,
                ))
            except (TypeError, ValueError) as exc:
                logger.warning(
                    "Se omitió una entrada inválida del feed %s (%s).",
                    source_name,
                    type(exc).__name__,
                )

        return items

    @staticmethod
    def _extract_search_keywords(user_text: str) -> str:
        """Extrae palabras clave de búsqueda quitando frases de relleno comunes en español e inglés."""
        cleaned = re.sub(
            r"^(sigue|buscar?|monitorear?|revisar?|rastrear?|analizar?|ver|atento a)\s+(las\s+noticias\s+(sobre|de|del)?|noticias\s+(sobre|de|del)?|informaci[oó]n\s+(sobre|de|del)?|a)?\s*",
            "",
            user_text,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"^(follow|search(?:\s+for)?|monitor|track|check|analyze|watch|look\s+for)\s+(the\s+latest\s+news\s+(?:about|on|for)|latest\s+news\s+(?:about|on|for)|the\s+news\s+(?:about|on|for)|news\s+(?:about|on|for)|information\s+(?:about|on))?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"\b(que\s+dio|que\s+dijo|seg[uú]n|according\s+to|what\s+did\s+say)\b",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = " ".join(cleaned.split()).strip()
        return cleaned if cleaned else user_text

    def fetch_search_news(self, query: str) -> List[NewsItem]:
        """Descarga noticias en tiempo real para una directiva o búsqueda personalizada usando Google News RSS."""
        import urllib.parse

        cleaned_query = self._extract_search_keywords(query)
        encoded_query = urllib.parse.quote_plus(cleaned_query)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=es-419&gl=AR&ceid=AR:es-419"

        items = self.fetch_feed(
            url,
            source_name=f"Google News: '{cleaned_query}'",
            category_name="Búsqueda Personalizada",
        )

        # Si la búsqueda limpia obtuvo pocas noticias y la frase original era distinta, complementar con la original
        if len(items) < 3 and cleaned_query.lower() != query.lower():
            encoded_raw = urllib.parse.quote_plus(query)
            raw_url = f"https://news.google.com/rss/search?q={encoded_raw}&hl=es-419&gl=AR&ceid=AR:es-419"
            raw_items = self.fetch_feed(
                raw_url,
                source_name=f"Google News: '{query}'",
                category_name="Búsqueda Personalizada",
            )
            for it in raw_items:
                if not any(existing.id == it.id for existing in items):
                    items.append(it)

        return items

    def collect_all(
        self,
        category_filter: Optional[str] = None,
        custom_query: Optional[str] = None,
    ) -> List[NewsItem]:
        """Descarga feeds configurados y opcionalmente noticias específicas para una directiva de búsqueda."""
        all_news: List[NewsItem] = []

        # 1. Si el usuario ingresó una directiva temática, buscar primero noticias específicas
        if custom_query and custom_query.strip():
            targeted_news = self.fetch_search_news(custom_query.strip())
            all_news.extend(targeted_news)

        # 2. Descargar feeds configurados en feeds.yaml
        feeds_config = settings.load_feeds()
        categories = feeds_config.get("categories", {})

        for cat_key, cat_data in categories.items():
            if category_filter and category_filter != cat_key:
                continue

            category_name = cat_data.get("name", cat_key)
            feeds = cat_data.get("feeds", [])

            for feed_info in feeds:
                name = feed_info.get("name", "Unknown")
                url = feed_info.get("url", "")
                if not url:
                    continue
                fetched = self.fetch_feed(url, source_name=name, category_name=category_name)
                all_news.extend(fetched)

        return all_news
