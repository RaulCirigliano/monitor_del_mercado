from typing import Optional
from pydantic import BaseModel, Field


class AssetSnapshot(BaseModel):
    """Instantánea de mercado obtenida mediante yfinance."""

    ticker: str = Field(description="Símbolo del activo (ej. BTC-USD, CL=F, NVDA, BABA)")
    name: str = Field(default="", description="Nombre de la empresa o activo")
    current_price: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False, description="Precio actual en mercado")
    currency: str = Field(default="USD", description="Moneda de cotización")
    change_pct_24h: Optional[float] = Field(default=None, allow_inf_nan=False, description="Variación porcentual respecto al cierre anterior")
    fifty_two_week_high: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False, description="Máximo en 52 semanas")
    fifty_two_week_low: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False, description="Mínimo en 52 semanas")
    pct_from_52w_high: Optional[float] = Field(default=None, allow_inf_nan=False, description="% de distancia desde el máximo anual")
    pct_from_52w_low: Optional[float] = Field(default=None, allow_inf_nan=False, description="% de distancia desde el mínimo anual")
    rsi_14: Optional[float] = Field(default=None, ge=0, le=100, allow_inf_nan=False, description="Índice de Fuerza Relativa (RSI de 14 períodos)")
    sma_50: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False, description="Media móvil simple de 50 períodos")
    ema_200: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False, description="Media móvil exponencial de 200 períodos")
    z_score_20: Optional[float] = Field(default=None, allow_inf_nan=False, description="Z-Score estadístico de 20 períodos")
    atr_14: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False, description="Average True Range de 14 períodos")
    atr_pct: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False, description="ATR(14) porcentual sobre el precio actual")
    rvol_20: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False, description="Volumen relativo respecto a la media de 20 períodos")
    sector: Optional[str] = Field(default=None, description="Sector económico o categoría de activo")

    def to_compact_text(self) -> str:
        """Formato compacto para alimentar al evaluador contrarian con métricas cuantitativas."""
        lines = [f"Activo: {self.ticker} ({self.name})"]
        if self.current_price is not None:
            lines.append(f"Precio actual: {self.current_price:.2f} {self.currency}")
        if self.change_pct_24h is not None:
            lines.append(f"Variación vs cierre anterior: {self.change_pct_24h:+.2f}%")
        if self.pct_from_52w_high is not None and self.pct_from_52w_low is not None:
            lines.append(f"Rango 52s: {self.pct_from_52w_high:.1f}% del Máx | +{self.pct_from_52w_low:.1f}% del Mín")
        if self.rsi_14 is not None:
            lines.append(f"RSI(14): {self.rsi_14:.1f}")
        if self.z_score_20 is not None:
            lines.append(f"Z-Score(20): {self.z_score_20:+.2f}")
        if self.sma_50 is not None:
            lines.append(f"SMA(50): {self.sma_50:.2f}")
        if self.ema_200 is not None:
            if self.current_price is not None and self.ema_200 > 0:
                pct_ema = ((self.current_price - self.ema_200) / self.ema_200) * 100.0
                lines.append(f"EMA(200): {self.ema_200:.2f} ({pct_ema:+.1f}%)")
            else:
                lines.append(f"EMA(200): {self.ema_200:.2f}")
        if self.atr_14 is not None:
            atr_str = f"ATR(14): {self.atr_14:.2f}"
            if self.atr_pct is not None:
                atr_str += f" ({self.atr_pct:.2f}%)"
            lines.append(atr_str)
        elif self.atr_pct is not None:
            lines.append(f"ATR%: {self.atr_pct:.2f}%")
        if self.rvol_20 is not None:
            lines.append(f"RVOL(20): {self.rvol_20:.2f}x")
        return " | ".join(lines)
