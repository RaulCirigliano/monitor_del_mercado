from typing import Optional
from pydantic import BaseModel, Field


class AssetSnapshot(BaseModel):
    """Instantánea de mercado obtenida mediante yfinance."""

    ticker: str = Field(description="Símbolo del activo (ej. BTC-USD, CL=F, NVDA, BABA)")
    name: str = Field(default="", description="Nombre de la empresa o activo")
    current_price: Optional[float] = Field(default=None, description="Precio actual en mercado")
    currency: str = Field(default="USD", description="Moneda de cotización")
    change_pct_24h: Optional[float] = Field(default=None, description="Variación porcentual de la última sesión")
    fifty_two_week_high: Optional[float] = Field(default=None, description="Máximo en 52 semanas")
    fifty_two_week_low: Optional[float] = Field(default=None, description="Mínimo en 52 semanas")
    pct_from_52w_high: Optional[float] = Field(default=None, description="% de distancia desde el máximo anual")
    pct_from_52w_low: Optional[float] = Field(default=None, description="% de distancia desde el mínimo anual")
    rsi_14: Optional[float] = Field(default=None, description="Índice de Fuerza Relativa (RSI de 14 períodos)")
    sector: Optional[str] = Field(default=None, description="Sector económico o categoría de activo")

    def to_compact_text(self) -> str:
        """Formato compacto para alimentar al evaluador contrarian."""
        lines = [f"Activo: {self.ticker} ({self.name})"]
        if self.current_price is not None:
            lines.append(f"Precio actual: {self.current_price:.2f} {self.currency}")
        if self.change_pct_24h is not None:
            lines.append(f"Var 24h: {self.change_pct_24h:+.2f}%")
        if self.pct_from_52w_high is not None and self.pct_from_52w_low is not None:
            lines.append(f"Rango 52s: {self.pct_from_52w_high:.1f}% del Máx | +{self.pct_from_52w_low:.1f}% del Mín")
        if self.rsi_14 is not None:
            lines.append(f"RSI (14): {self.rsi_14:.1f}")
        return " | ".join(lines)
