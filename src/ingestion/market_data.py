from typing import Dict, Optional
import yfinance as yf
import pandas as pd

from src.models import AssetSnapshot


class MarketDataFetcher:
    """Obtiene cotizaciones y métricas técnicas de mercado usando yfinance."""

    def __init__(self):
        self._cache: Dict[str, AssetSnapshot] = {}

    def _calculate_rsi(self, series: pd.Series, period: int = 14) -> Optional[float]:
        """Calcula el RSI clásico de Wilder para una serie de precios de cierre."""
        if len(series) < period + 1:
            return None

        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.rolling(window=period, min_periods=period).mean()
        avg_loss = loss.rolling(window=period, min_periods=period).mean()

        last_gain = avg_gain.iloc[-1]
        last_loss = avg_loss.iloc[-1]

        if pd.isna(last_gain) or pd.isna(last_loss):
            return None
        if last_loss == 0:
            return 100.0

        rs = last_gain / last_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return round(float(rsi), 2)

    def get_snapshot(self, ticker: str) -> Optional[AssetSnapshot]:
        """Obtiene la instantánea de cotización y métricas técnicas para un ticker."""
        ticker = ticker.strip().upper()
        if not ticker:
            return None

        if ticker in self._cache:
            return self._cache[ticker]

        try:
            yt = yf.Ticker(ticker)
            # Descargamos 2 meses de datos para calcular RSI(14) y variación diaria confiable
            hist = yt.history(period="2mo")

            if hist.empty or "Close" not in hist.columns:
                return None

            close_series = hist["Close"].dropna()
            if len(close_series) == 0:
                return None

            current_price = float(close_series.iloc[-1])
            prev_price = float(close_series.iloc[-2]) if len(close_series) >= 2 else current_price

            change_pct = ((current_price - prev_price) / prev_price) * 100.0 if prev_price > 0 else 0.0

            # Metadatos del activo (info puede ser lento o parcial en yfinance)
            info = {}
            try:
                info = yt.fast_info
                high_52 = getattr(info, "year_high", None)
                low_52 = getattr(info, "year_low", None)
                currency = getattr(info, "currency", "USD") or "USD"
            except Exception:
                high_52 = float(close_series.max())
                low_52 = float(close_series.min())
                currency = "USD"

            if high_52 is None:
                high_52 = float(close_series.max())
            if low_52 is None:
                low_52 = float(close_series.min())

            pct_from_high = ((current_price - high_52) / high_52) * 100.0 if high_52 and high_52 > 0 else 0.0
            pct_from_low = ((current_price - low_52) / low_52) * 100.0 if low_52 and low_52 > 0 else 0.0

            rsi_val = self._calculate_rsi(close_series, period=14)

            snapshot = AssetSnapshot(
                ticker=ticker,
                name=ticker,
                current_price=round(current_price, 4),
                currency=currency,
                change_pct_24h=round(change_pct, 2),
                fifty_two_week_high=round(high_52, 4) if high_52 else None,
                fifty_two_week_low=round(low_52, 4) if low_52 else None,
                pct_from_52w_high=round(pct_from_high, 2),
                pct_from_52w_low=round(pct_from_low, 2),
                rsi_14=rsi_val,
            )

            self._cache[ticker] = snapshot
            return snapshot

        except Exception:
            return None
