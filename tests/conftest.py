from pathlib import Path

import pymupdf
import pytest

from vespera.review.models import (
    AIAspectAssessment,
    AIAssessment,
    ChunkFindings,
    CriterionAssessment,
    CrossDocumentFindings,
    DocumentSummary,
    ExtractedMetrics,
    MultipleProposal,
    CriteriaChecks,
    CriterionCheck,
    ScoreRationale,
    ThesisAssessment,
    TriageItem,
    TriageResult,
)


class FakeProvider:
    """LLMProvider stand-in that returns canned responses, no network."""

    def __init__(
        self,
        chunk_findings=None,
        summary=None,
        cross_findings=None,
        metrics=None,
        thesis_assessment=None,
        multiple_proposal=None,
        ai_assessment=None,
        criteria_checks=None,
    ):
        self.chunk_findings = chunk_findings or []
        self.summary = summary
        self.cross_findings = cross_findings or []
        self.metrics = metrics or []
        self.thesis_assessment = thesis_assessment
        self.multiple_proposal = multiple_proposal
        self.ai_assessment = ai_assessment
        self.criteria_checks = criteria_checks
        self.prompts: list[str] = []

    def generate_structured(self, prompt, schema):
        self.prompts.append(prompt)
        if schema is ChunkFindings:
            return ChunkFindings(findings=self.chunk_findings)
        if schema is DocumentSummary:
            if self.summary is None:
                return DocumentSummary(doc_kind="other", contract_type="unknown", signed=False)
            return self.summary
        if schema is CrossDocumentFindings:
            return CrossDocumentFindings(findings=self.cross_findings)
        if schema is ExtractedMetrics:
            return ExtractedMetrics(metrics=self.metrics)
        if schema is ScoreRationale:
            return ScoreRationale(rationale="Signals are mixed; see findings.")
        if schema is ThesisAssessment:
            return self.thesis_assessment or ThesisAssessment(
                assessments=[
                    CriterionAssessment(
                        criterion="ARR scale", verdict="aligned", evidence="financials"
                    )
                ]
            )
        if schema is AIAssessment:
            return self.ai_assessment or AIAssessment(
                aspects=[
                    AIAspectAssessment(
                        aspect="product",
                        verdict="unclear",
                        detail="no coverage",
                        evidence="none",
                    )
                ],
                automation_leverage="Not assessable from the evidence.",
            )
        if schema is CriteriaChecks:
            return self.criteria_checks or CriteriaChecks(
                checks=[CriterionCheck(criterion="ARR scale", status="met", evidence="07")]
            )
        if schema is TriageResult:
            return TriageResult(
                items=[
                    TriageItem(title="IP conflict", direction="deal-breaker", why="x", source="03"),
                    TriageItem(title="No financials", direction="concern", why="x", source="room"),
                    TriageItem(title="Strong retention", direction="strength", why="x", source="07"),
                ],
                missing_essentials=["historical financials"],
                verdict="resolve the flagged items before a full review",
                rationale="One unresolved deal-breaker and missing financials.",
            )
        if schema is MultipleProposal:
            if self.multiple_proposal is None:
                return MultipleProposal(
                    basis="arr",
                    multiple_low=4.0,
                    multiple_base=6.0,
                    multiple_high=8.0,
                    sector="B2B software",
                    assumptions=["test assumption"],
                    confidence=0.6,
                )
            return self.multiple_proposal
        raise AssertionError(f"unexpected schema {schema}")


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "contract.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "This Agreement may be terminated for convenience.")
    page2 = doc.new_page()
    page2.insert_text((72, 72), "Governing law: England and Wales.")
    doc.save(path)
    doc.close()
    return path
