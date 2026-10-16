import logging
import math
import time
from typing import Dict, Optional
import yfinance as yf
import pandas as pd

from src.models import AssetSnapshot

logger = logging.getLogger(__name__)


class MarketDataFetcher:
    """Obtiene cotizaciones y métricas técnicas de mercado usando yfinance."""

    DEFAULT_CACHE_TTL = 300.0  # 5 minutos de TTL para evitar precios obsoletos en modo continuo

    def __init__(self, cache_ttl: float = DEFAULT_CACHE_TTL):
        self._cache: Dict[str, AssetSnapshot] = {}
        self._cache_timestamps: Dict[str, float] = {}
        self.cache_ttl: float = float(cache_ttl)

    def _calculate_rsi(self, series: pd.Series, period: int = 14) -> Optional[float]:
        """Calcula el RSI clásico de Wilder para una serie de precios de cierre."""
        if len(series) < period + 1:
            return None

        changes = series.diff().dropna()
        if len(changes) < period:
            return None

        gains = changes.clip(lower=0)
        losses = -changes.clip(upper=0)
        avg_gain = float(gains.iloc[:period].mean())
        avg_loss = float(losses.iloc[:period].mean())
        for gain, loss in zip(gains.iloc[period:], losses.iloc[period:]):
            avg_gain = ((period - 1) * avg_gain + float(gain)) / period
            avg_loss = ((period - 1) * avg_loss + float(loss)) / period

        if avg_loss == 0 and avg_gain == 0:
            return 50.0
        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return round(float(rsi), 2)

    def _calculate_sma(self, series: pd.Series, period: int = 50) -> Optional[float]:
        """Calcula la media móvil simple (SMA) para el período indicado."""
        if len(series) < period:
            return None
        val = self._positive_finite(series.iloc[-period:].mean())
        return round(val, 4) if val is not None else None

    def _calculate_ema(self, series: pd.Series, span: int = 200) -> Optional[float]:
        """Calcula la media móvil exponencial (EMA) cuando hay historial suficiente."""
        if len(series) < 20:
            return None
        ema_val = series.ewm(span=span, adjust=False).mean().iloc[-1]
        val = self._positive_finite(ema_val)
        return round(val, 4) if val is not None else None

    @staticmethod
    def _calculate_z_score(series: pd.Series, period: int = 20) -> Optional[float]:
        """Calcula el Z-Score estadístico respecto a la media y desviación estándar de `period` ruedas."""
        if len(series) < period:
            return None
        window = series.iloc[-period:]
        mean_val = float(window.mean())
        std_val = float(window.std(ddof=0))
        if not math.isfinite(mean_val) or not math.isfinite(std_val):
            return None
        if std_val == 0:
            return 0.0
        z_val = (float(window.iloc[-1]) - mean_val) / std_val
        return round(z_val, 2) if math.isfinite(z_val) else None

    def _calculate_atr(self, hist: pd.DataFrame, period: int = 14) -> Optional[float]:
        """Calcula el Average True Range (ATR) de `period` períodos."""
        if not {"High", "Low", "Close"}.issubset(hist.columns):
            return None
        df = hist[["High", "Low", "Close"]].apply(pd.to_numeric, errors="coerce").dropna()
        if len(df) < period:
            return None
        prev_close = df["Close"].shift(1)
        tr = pd.concat(
            [
                (df["High"] - df["Low"]).abs(),
                (df["High"] - prev_close).abs(),
                (df["Low"] - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1).dropna()
        if len(tr) < period:
            return None
        atr_val = float(tr.iloc[:period].mean())
        for tr_i in tr.iloc[period:]:
            atr_val = ((period - 1) * atr_val + float(tr_i)) / period
        val = self._positive_finite(atr_val)
        return round(val, 4) if val is not None else None

    @staticmethod
    def _calculate_rvol(hist: pd.DataFrame, period: int = 20) -> Optional[float]:
        """Calcula el Volumen Relativo (RVOL) frente al promedio de las últimas `period` ruedas."""
        if "Volume" not in hist.columns:
            return None
        vol_series = pd.to_numeric(hist["Volume"], errors="coerce").dropna()
        if len(vol_series) < period:
            return None
        avg_vol = float(vol_series.iloc[-period:].mean())
        last_vol = float(vol_series.iloc[-1])
        if not math.isfinite(avg_vol) or not math.isfinite(last_vol) or avg_vol <= 0 or last_vol < 0:
            return None
        return round(last_vol / avg_vol, 2)

    @staticmethod
    def _positive_finite(value) -> Optional[float]:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) and number > 0 else None

    def get_snapshot(self, ticker: str) -> Optional[AssetSnapshot]:
        """Obtiene la instantánea de cotización y métricas técnicas para un ticker con caché TTL."""
        ticker = ticker.strip().upper()
        if not ticker:
            return None

        now_mono = time.monotonic()
        if ticker in self._cache:
            cached_at = self._cache_timestamps.get(ticker)
            if cached_at is not None and (now_mono - cached_at) < self.cache_ttl:
                return self._cache[ticker]
            self._cache.pop(ticker, None)
            self._cache_timestamps.pop(ticker, None)

        try:
            yt = yf.Ticker(ticker)
            # Un año de datos evita reemplazar los extremos anuales por los de solo dos meses.
            hist = yt.history(period="1y")

            if hist.empty or "Close" not in hist.columns:
                return None

            close_series = pd.to_numeric(hist["Close"], errors="coerce").dropna()
            if len(close_series) == 0:
                return None

            current_price = self._positive_finite(close_series.iloc[-1])
            if current_price is None:
                return None
            prev_price = (
                self._positive_finite(close_series.iloc[-2])
                if len(close_series) >= 2
                else None
            )

            # Metadatos del activo (info puede ser lento o parcial en yfinance)
            try:
                info = yt.fast_info
                high_52 = getattr(info, "year_high", None)
                low_52 = getattr(info, "year_low", None)
                currency = getattr(info, "currency", "USD") or "USD"
                last_price = getattr(info, "last_price", None)
                previous_close = getattr(info, "previous_close", None)
            except Exception:
                high_52 = None
                low_52 = None
                currency = "USD"
                last_price = None
                previous_close = None

            current_price = self._positive_finite(last_price) or current_price
            prev_price = self._positive_finite(previous_close) or prev_price
            change_pct = (
                ((current_price - prev_price) / prev_price) * 100.0
                if prev_price is not None
                else None
            )

            high_52 = self._positive_finite(high_52)
            low_52 = self._positive_finite(low_52)
            if high_52 is None and "High" in hist.columns:
                high_series = pd.to_numeric(hist["High"], errors="coerce").dropna()
                high_52 = self._positive_finite(high_series.max()) if not high_series.empty else None
            if low_52 is None and "Low" in hist.columns:
                low_series = pd.to_numeric(hist["Low"], errors="coerce").dropna()
                low_52 = self._positive_finite(low_series.min()) if not low_series.empty else None

            pct_from_high = (
                ((current_price - high_52) / high_52) * 100.0
                if high_52 is not None
                else None
            )
            pct_from_low = (
                ((current_price - low_52) / low_52) * 100.0
                if low_52 is not None
                else None
            )

            rsi_val = self._calculate_rsi(close_series, period=14)
            sma_50_val = self._calculate_sma(close_series, period=50)
            ema_200_val = self._calculate_ema(close_series, span=200)
            z_score_20_val = self._calculate_z_score(close_series, period=20)
            atr_14_val = self._calculate_atr(hist, period=14)
            atr_pct_val = (
                round((atr_14_val / current_price) * 100.0, 2)
                if atr_14_val is not None and current_price > 0
                else None
            )
            rvol_20_val = self._calculate_rvol(hist, period=20)

            snapshot = AssetSnapshot(
                ticker=ticker,
                name=ticker,
                current_price=round(current_price, 4),
                currency=currency,
                change_pct_24h=round(change_pct, 2) if change_pct is not None else None,
                fifty_two_week_high=round(high_52, 4) if high_52 is not None else None,
                fifty_two_week_low=round(low_52, 4) if low_52 is not None else None,
                pct_from_52w_high=round(pct_from_high, 2) if pct_from_high is not None else None,
                pct_from_52w_low=round(pct_from_low, 2) if pct_from_low is not None else None,
                rsi_14=rsi_val,
                sma_50=sma_50_val,
                ema_200=ema_200_val,
                z_score_20=z_score_20_val,
                atr_14=atr_14_val,
                atr_pct=atr_pct_val,
                rvol_20=rvol_20_val,
            )

            self._cache[ticker] = snapshot
            self._cache_timestamps[ticker] = time.monotonic()
            return snapshot

        except Exception as e:
            logger.warning("No se pudo obtener la cotización de %s: %s", ticker, e)
            return None
