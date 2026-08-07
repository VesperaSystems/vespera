"""Configuration defaults for a review run."""

import os
from dataclasses import dataclass, field
from pathlib import Path

# recommended models, fastest first; the default is the fastest
RECOMMENDED_MODELS: list[tuple[str, str]] = [
    ("qwen3:4b", "faster"),
    ("qwen3:8b", "more thorough"),
]
DEFAULT_MODEL = RECOMMENDED_MODELS[0][0]
DEFAULT_OLLAMA_HOST = os.environ.get("VESPERA_OLLAMA_HOST", "http://localhost:11434")


@dataclass
class ReviewConfig:
    model: str = DEFAULT_MODEL
    ollama_host: str = DEFAULT_OLLAMA_HOST
    chunk_chars: int = 7000
    chunk_overlap_chars: int = 400
    max_evidence_chars: int = 300
    output_dir: Path = field(default_factory=lambda: Path("vespera-output"))
