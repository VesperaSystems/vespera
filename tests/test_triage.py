from pathlib import Path

import pytest
from conftest import FakeProvider
from pydantic import ValidationError

from vespera.review.models import TriageItem, TriageResult
from vespera.review.triage import triage_dataroom


def build_room(tmp_path: Path) -> Path:
    room = tmp_path / "room"
    room.mkdir()
    (room / "contract.txt").write_text("An agreement between two parties.")
    (room / "note.txt").write_text("A meeting note.")
    return room


def test_triage_runs_summaries_and_synthesis(tmp_path):
    provider = FakeProvider()
    outcome = triage_dataroom(build_room(tmp_path), provider=provider)
    assert len(outcome.documents) == 2
    assert len(outcome.result.items) == 3
    assert outcome.result.verdict == "resolve the flagged items before a full review"
    # one summary call per document plus one synthesis call
    assert len(provider.prompts) == 3


def test_triage_includes_thesis_when_given(tmp_path):
    room = build_room(tmp_path)
    thesis = tmp_path / "thesis.md"
    thesis.write_text("We invest in B2B software.")
    provider = FakeProvider()
    triage_dataroom(room, thesis_path=thesis, provider=provider)
    assert "INVESTMENT CRITERIA" in provider.prompts[-1]
    assert "B2B software" in provider.prompts[-1]


def test_triage_survives_failed_summary(tmp_path):
    from vespera.llm.ollama import OllamaError
    from vespera.review.models import DocumentSummary

    class FailOnFirstSummary(FakeProvider):
        def __init__(self):
            super().__init__()
            self.failed = False

        def generate_structured(self, prompt, schema):
            if schema is DocumentSummary and not self.failed:
                self.failed = True
                raise OllamaError("bad output")
            return super().generate_structured(prompt, schema)

    outcome = triage_dataroom(build_room(tmp_path), provider=FailOnFirstSummary())
    assert len(outcome.degraded_documents) == 1
    assert len(outcome.result.items) == 3


def test_triage_result_requires_exactly_three_items():
    item = TriageItem(title="x", direction="concern", why="y", source="z")
    with pytest.raises(ValidationError):
        TriageResult(items=[item], verdict="full review looks worthwhile", rationale="r")
    with pytest.raises(ValidationError):
        TriageResult(items=[item] * 4, verdict="full review looks worthwhile", rationale="r")
