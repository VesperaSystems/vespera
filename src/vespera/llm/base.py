"""Minimal LLM provider interface so the backend stays replaceable."""

from typing import Protocol

from pydantic import BaseModel


class LLMProvider(Protocol):
    def generate_structured(self, prompt: str, schema: type[BaseModel]) -> BaseModel: ...
