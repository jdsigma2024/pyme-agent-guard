from __future__ import annotations

import httpx

from pyme_guard.domain.errors import LLMUnavailableError


class OllamaLLM:
    """Adaptador para Ollama (API REST local). Sin SDK: menos superficie de ataque."""

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._model = model
        self._client = client or httpx.Client(base_url=base_url, timeout=timeout)

    def generate(self, system_prompt: str, user_message: str) -> str:
        payload = {
            "model": self._model,
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 400},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        }
        try:
            response = self._client.post("/api/chat", json=payload)
            response.raise_for_status()
            return str(response.json()["message"]["content"])
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise LLMUnavailableError("Ollama no respondió correctamente") from exc
