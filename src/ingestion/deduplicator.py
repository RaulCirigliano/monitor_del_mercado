import hashlib
import re
from typing import Set, Tuple


class Deduplicator:
    """Filtro en memoria para descartar duplicados y titulares de spam/ruido evidente."""

    # Palabras clave y frases típicas de contenido basura o spam publicitario
    NOISE_PATTERNS = [
        r"\b(sponsored|advertisement|patrocinado|ad)\b",
        r"\b(top \d+ stocks to buy now|stocks to watch today)\b",
        r"\b(motley fool issues rare|here is why you should buy)\b",
        r"\b(crypto casino|airdrop alert|claim free)\b",
        r"\b(best meme coins to buy|1000x potential)\b",
    ]

    def __init__(self):
        self._seen_hashes: Set[str] = set()
        self._noise_regexes = [re.compile(p, re.IGNORECASE) for p in self.NOISE_PATTERNS]

    def _normalize_text(self, text: str) -> str:
        """Normaliza el texto para comparación aproximada."""
        text = text.lower().strip()
        return re.sub(r"[^\w\s]", "", text)

    def is_noise(self, title: str, summary: str = "") -> bool:
        """Evalúa si el titular coincide con patrones explícitos de ruido/publicidad."""
        combined = f"{title} {summary}"
        for regex in self._noise_regexes:
            if regex.search(combined):
                return True
        return False

    def is_duplicate(self, title: str, link: str = "") -> bool:
        """Verifica si el titular o enlace ya ha sido registrado en memoria en este ciclo."""
        norm_title = self._normalize_text(title)
        title_hash = hashlib.sha256(norm_title.encode("utf-8")).hexdigest()

        # Normalizar enlace descartando query params (UTM, tracking)
        clean_link = link.split("?")[0].strip() if link else ""
        link_hash = hashlib.sha256(clean_link.encode("utf-8")).hexdigest() if clean_link else None

        if title_hash in self._seen_hashes or (link_hash and link_hash in self._seen_hashes):
            return True

        self._seen_hashes.add(title_hash)
        if link_hash:
            self._seen_hashes.add(link_hash)
        return False

    def reset(self) -> None:
        """Limpia los hashes en memoria para un nuevo ciclo de ejecución."""
        self._seen_hashes.clear()
