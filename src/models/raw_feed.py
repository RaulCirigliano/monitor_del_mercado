from typing import List, Optional
from pydantic import BaseModel, Field


class NewsItem(BaseModel):
    """Representa una noticia o evento ingestada desde un feed RSS."""

    id: str = Field(description="Hash único identificador del contenido")
    title: str = Field(description="Titular de la noticia")
    link: str = Field(description="Enlace directo a la fuente")
    source: str = Field(description="Nombre de la fuente (ej. Yahoo Finance, OilPrice)")
    category: str = Field(description="Categoría temática del feed")
    published: Optional[str] = Field(default=None, description="Fecha de publicación original")
    summary: str = Field(default="", description="Texto limpio del resumen o cuerpo")
    tickers_detected: List[str] = Field(default_factory=list, description="Lista de tickers identificados")

    def to_compact_text(self) -> str:
        """Genera una versión concisa para el prompt del LLM."""
        tickers_str = f" [Tickers: {', '.join(self.tickers_detected)}]" if self.tickers_detected else ""
        return f"[{self.source} | {self.category}] {self.title}{tickers_str}\nResumen: {self.summary[:280]}"
