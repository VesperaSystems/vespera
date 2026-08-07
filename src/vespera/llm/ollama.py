"""Ollama-backed LLM provider using the local HTTP API."""

import httpx
from pydantic import BaseModel, ValidationError


class OllamaError(RuntimeError):
    pass


class OllamaProvider:
    def __init__(self, model: str, host: str = "http://localhost:11434", timeout: float = 300.0):
        self.model = model
        self.host = host.rstrip("/")
        self._client = httpx.Client(base_url=self.host, timeout=timeout)

    def generate_structured(self, prompt: str, schema: type[BaseModel]) -> BaseModel:
        last_error: Exception | None = None
        for _ in range(2):  # one retry on invalid output
            content = self._chat(prompt, schema)
            try:
                return schema.model_validate_json(content)
            except ValidationError as error:
                last_error = error
        raise OllamaError(f"Model returned output that failed validation twice: {last_error}")

    def _chat(self, prompt: str, schema: type[BaseModel]) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": schema.model_json_schema(),
            "think": False,
            "options": {"temperature": 0.1},
        }
        try:
            response = self._client.post("/api/chat", json=payload)
            response.raise_for_status()
        except httpx.ConnectError as error:
            raise OllamaError(
                f"Cannot reach Ollama at {self.host}. Is it running? "
                "Install from https://ollama.com and run: ollama serve"
            ) from error
        except httpx.HTTPStatusError as error:
            detail = error.response.text[:300]
            if error.response.status_code == 404:
                raise OllamaError(
                    f"Model '{self.model}' not found. Pull it first: ollama pull {self.model}"
                ) from error
            raise OllamaError(f"Ollama request failed: {detail}") from error
        return response.json()["message"]["content"]

    def list_local_models(self) -> list[str]:
        try:
            response = self._client.get("/api/tags")
            response.raise_for_status()
        except httpx.HTTPError:
            return []
        return [item["name"] for item in response.json().get("models", [])]
