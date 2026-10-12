import json
import re
from typing import Any, Dict, Optional
from config import settings


class GeminiClient:
    """Cliente opcional para Google Gemini 2.0 Flash (Cloud gratuito) para análisis de texto extenso."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.gemini_api_key
        self.model = model or settings.gemini_model
        self._client = None

        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except Exception:
                self._client = None

    def is_available(self) -> bool:
        """Determina si la API key está presente y la librería configurada."""
        return bool(self.api_key and self._client is not None)

    def _clean_json_response(self, text: str) -> str:
        text = text.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            return match.group(1).strip()
        return text

    def generate_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """Envía el análisis a Gemini 2.0 Flash solicitando formato JSON."""
        if not self.is_available():
            raise RuntimeError("Gemini Client no está configurado (falta GEMINI_API_KEY).")

        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            temperature=0.2,
        )

        response = self._client.models.generate_content(
            model=self.model,
            contents=user_prompt,
            config=config,
        )

        cleaned = self._clean_json_response(response.text)
        return json.loads(cleaned)
