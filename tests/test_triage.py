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


def test_violated_criterion_takes_a_slot():
    from vespera.review.models import CriterionCheck
    from vespera.review.triage import apply_criteria_checks

    all_strengths = TriageResult(
        items=[
            TriageItem(title="Growth", direction="strength", why="x", source="07"),
            TriageItem(title="Margin", direction="strength", why="x", source="07"),
            TriageItem(title="Retention", direction="strength", why="x", source="07"),
        ],
        verdict="full review looks worthwhile",
        rationale="all good",
    )
    checks = [
        CriterionCheck(criterion="ARR scale", status="met", evidence="07"),
        CriterionCheck(
            criterion="Clean IP ownership including contractors",
            status="violated",
            evidence="03 vs 05",
        ),
    ]
    result = apply_criteria_checks(all_strengths, checks)
    breakers = [i for i in result.items if i.direction == "deal-breaker"]
    assert len(breakers) == 1
    assert "Clean IP" in breakers[0].title
    assert result.verdict == "significant deal-breakers evident"


def test_already_covered_violation_not_duplicated():
    from vespera.review.models import CriterionCheck
    from vespera.review.triage import apply_criteria_checks

    covering = TriageResult(
        items=[
            TriageItem(
                title="Disputed ownership of firmware intellectual property",
                direction="deal-breaker",
                why="x",
                source="03",
            ),
            TriageItem(title="Margin", direction="strength", why="x", source="07"),
            TriageItem(title="Retention", direction="strength", why="x", source="07"),
        ],
        verdict="significant deal-breakers evident",
        rationale="ip",
    )
    checks = [
        CriterionCheck(criterion="Clean intellectual property", status="violated", evidence="03")
    ]
    result = apply_criteria_checks(covering, checks)
    assert sum(1 for i in result.items if i.direction == "deal-breaker") == 1


def test_triage_result_requires_exactly_three_items():
    item = TriageItem(title="x", direction="concern", why="y", source="z")
    with pytest.raises(ValidationError):
        TriageResult(items=[item], verdict="full review looks worthwhile", rationale="r")
    with pytest.raises(ValidationError):
        TriageResult(items=[item] * 4, verdict="full review looks worthwhile", rationale="r")
