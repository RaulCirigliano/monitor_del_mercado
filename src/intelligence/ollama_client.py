import json
import re
from typing import Any, Dict, Optional
import httpx

from config import settings


class OllamaClient:
    """Cliente HTTP para interactuar con la API local de Ollama de forma ultrarrápida."""

    def __init__(self, host: Optional[str] = None, model: Optional[str] = None, timeout: Optional[float] = None):
        self.host = (host or settings.ollama_host).rstrip("/")
        self.model = model or settings.ollama_model
        self.timeout = timeout or settings.ollama_timeout

    def is_available(self) -> bool:
        """Verifica si el servicio de Ollama está activo en el puerto configurado."""
        try:
            with httpx.Client(timeout=3.0) as client:
                res = client.get(f"{self.host}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    def _clean_json_response(self, text: str) -> str:
        """Remueve bloques ```json y caracteres espurios si el modelo los incluye."""
        text = text.strip()
        # Eliminar etiquetas markdown de bloques de código
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            text = match.group(1).strip()
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]
        return text

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 400,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Envía el prompt a Ollama respetando el timeout configurado."""
        url = f"{self.host}/api/chat"
        call_timeout = timeout or self.timeout

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.2,
                "top_p": 0.9,
                "num_predict": max_tokens,  # Evita que el modelo se pierda en respuestas infinitas
            },
        }

        try:
            timeout_cfg = httpx.Timeout(call_timeout, connect=10.0, read=call_timeout)
            with httpx.Client(timeout=timeout_cfg) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

            content = data.get("message", {}).get("content", "")
            cleaned = self._clean_json_response(content)
            return json.loads(cleaned)

        except (httpx.ReadTimeout, httpx.ConnectTimeout) as e:
            raise TimeoutError(f"Tiempo máximo alcanzado ({call_timeout}s) esperando respuesta de Ollama.")
        except json.JSONDecodeError as e:
            raise ValueError(f"Ollama devolvió un JSON incompleto o inválido: {e}. Contenido: {content[:200]}")
        except Exception as e:
            raise RuntimeError(f"Error comunicando con Ollama en {self.host}: {e}")
