"""Ollama-backed LLM provider using the local HTTP API."""

import json
from typing import Iterator

import httpx
from pydantic import BaseModel, ValidationError


def model_matches(requested: str, available: list[str]) -> bool:
    """True if the requested model name is in the available list.

    Ollama lists untagged pulls as "name:latest", so "qwen3" matches "qwen3:latest".
    """
    if requested in available:
        return True
    return ":" not in requested and f"{requested}:latest" in available


class OllamaError(RuntimeError):
    pass


def _repair_truncated_json(content: str) -> list[str]:
    """Candidate completions for JSON cut off mid-generation.

    Walks back to the last few complete '}' and tries plausible closers, so a list
    of 100 objects truncated inside object 101 still yields the first 100.
    """
    candidates = []
    idx = len(content)
    for _ in range(4):
        idx = content.rfind("}", 0, idx)
        if idx <= 0:
            break
        base = content[: idx + 1]
        for closer in ("", "]", "}", "]}", "}]", "]}}"):
            candidates.append(base + closer)
        idx -= 1
    return candidates


class OllamaProvider:
    def __init__(
        self,
        model: str,
        host: str = "http://localhost:11434",
        timeout: float = 900.0,
        think: bool = False,
    ):
        self.model = model
        self.host = host.rstrip("/")
        self.think = think
        self._client = httpx.Client(base_url=self.host, timeout=timeout)

    def generate_structured(self, prompt: str, schema: type[BaseModel]) -> BaseModel:
        last_error: Exception | None = None
        for _ in range(2):  # one retry on invalid output
            content = self._chat(prompt, schema)
            try:
                return schema.model_validate_json(content)
            except ValidationError as error:
                last_error = error
            # output truncated at the generation cap is the common failure; try to
            # salvage the complete objects before paying for another model call
            for candidate in _repair_truncated_json(content):
                try:
                    return schema.model_validate_json(candidate)
                except ValidationError:
                    continue
        raise OllamaError(f"Model returned output that failed validation twice: {last_error}")

    def _chat(self, prompt: str, schema: type[BaseModel]) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": schema.model_json_schema(),
            "think": self.think,
            "options": {
                "temperature": 0.1,
                # Ollama's default 4k context truncates larger prompts, which can send
                # thinking models into runaway generation; num_predict caps that too
                "num_ctx": 16384,
                "num_predict": 8192,
            },
        }
        try:
            response = self._client.post("/api/chat", json=payload)
            response.raise_for_status()
        except httpx.ConnectError as error:
            raise OllamaError(
                f"Cannot reach Ollama at {self.host}. Is it running? "
                "Install from https://ollama.com and run: ollama serve"
            ) from error
        except httpx.TimeoutException as error:
            raise OllamaError(
                f"The model took longer than {self._client.timeout.read:.0f}s to respond. "
                "The machine may be under heavy load — close other applications and retry, "
                "or use a smaller model (vespera models)."
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

    def is_server_running(self) -> bool:
        try:
            self._client.get("/api/version").raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    def has_model(self) -> bool:
        return model_matches(self.model, self.list_local_models())

    def pull_model(self) -> Iterator[dict]:
        """Pull the model, yielding Ollama progress events ({status, total?, completed?})."""
        with self._client.stream(
            "POST", "/api/pull", json={"model": self.model}, timeout=None
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.strip():
                    continue
                event = json.loads(line)
                if "error" in event:
                    raise OllamaError(f"Could not download model '{self.model}': {event['error']}")
                yield event
