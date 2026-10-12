from pathlib import Path
import os
import yaml
from dotenv import load_dotenv

# Cargar variables de entorno desde .env si existe
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    """Configuración central del Monitor del Mercado."""

    def __init__(self):
        self.base_dir: Path = BASE_DIR
        self.reports_dir: Path = BASE_DIR / "reportes"
        self.config_dir: Path = BASE_DIR / "config"
        self.feeds_file: Path = self.config_dir / "feeds.yaml"

        # Garantizar que el directorio de reportes exista
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        # Ollama local
        self.ollama_host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        self.ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
        self.ollama_timeout: float = float(os.getenv("OLLAMA_TIMEOUT", "180"))

        # Gemini Cloud (motor secundario opcional)
        self.gemini_api_key: str = os.getenv("GEMINI_API_KEY", "").strip()
        self.gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

        # Filtros de asimetría y muestreo
        self.min_risk_reward_ratio: float = float(os.getenv("MIN_RISK_REWARD_RATIO", "3.0"))
        self.max_items_per_feed: int = int(os.getenv("MAX_ITEMS_PER_FEED", "10"))
        self.days_back: int = int(os.getenv("DAYS_BACK", "3"))

    def load_feeds(self) -> dict:
        """Carga la configuración de fuentes RSS desde feeds.yaml."""
        if not self.feeds_file.exists():
            return {}
        with open(self.feeds_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}


settings = Settings()
