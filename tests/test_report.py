import json
from pathlib import Path

from vespera.deal import DealAnalysis
from vespera.review.models import (
    AIAspectAssessment,
    AIProfile,
    Finding,
    KeyMetric,
    ReadinessScore,
    ThesisFit,
    ThesisPoint,
    ValuationResult,
)
from vespera.review.report import render_markdown, write_outputs
from vespera.review.risks import risk_matrix

FINDINGS = [
    Finding(
        category="change-of-control clauses",
        title="Change of control triggers termination",
        summary="Counterparty may terminate on change of control.",
        severity="high",
        source_file="msa.pdf",
        source_page=1,
        evidence="Halcyon may terminate this Agreement immediately",
        confidence=0.92,
    ),
    Finding(
        category="governing law",
        title="English governing law",
        summary="Agreement governed by the laws of England and Wales.",
        severity="info",
        source_file="msa.pdf",
        source_page=2,
        evidence="governed by the laws of England and Wales",
        confidence=0.99,
    ),
]

METRIC = KeyMetric(
    name="arr",
    value_text="£9.6 million",
    amount=9.6,
    unit="GBP",
    period="FY2025",
    source_file="financials.pdf",
    source_page=1,
    evidence="ARR basis was £9.6 million",
)

VALUATION = ValuationResult(
    basis_metric="arr",
    basis_amount_millions=9.6,
    currency="GBP",
    multiple_low=4.0,
    multiple_base=6.0,
    multiple_high=8.0,
    value_low_millions=38.4,
    value_base_millions=57.6,
    value_high_millions=76.8,
    sector="B2B software",
    assumptions=["Growth persists"],
    confidence=0.6,
    caveats=["Churn unknown"],
)


def make_analysis(**overrides) -> DealAnalysis:
    base = dict(
        documents=["msa.pdf", "financials.pdf"],
        empty_documents=[],
        metrics=[METRIC],
        findings=FINDINGS,
        risk_matrix=risk_matrix(FINDINGS),
        score=ReadinessScore(score=72, label="Strong reading", rationale="Mostly clean."),
        ai_profile=AIProfile(
            posture="AI claimed, not evidenced",
            product_ai="claimed-only",
            aspects=[
                AIAspectAssessment(
                    aspect="product",
                    verdict="claimed-only",
                    detail="'AI-powered' platform claim",
                    evidence="product overview",
                )
            ],
            automation_leverage="Support workflows look addressable.",
        ),
        thesis_fit=ThesisFit(
            score=61,
            aligned=[ThesisPoint(point="ARR above £5m", evidence="financials.pdf")],
            conflicts=[ThesisPoint(point="IP not owned outright", evidence="contract 03")],
            unknowns=["Cap table quality"],
        ),
        valuation=VALUATION,
    )
    base.update(overrides)
    return DealAnalysis(**base)


def test_report_contains_all_sections():
    markdown = render_markdown(make_analysis())
    for section in [
        "# Vespera Deal Review",
        "Deal readiness: 72/100 — Strong reading",
        "## Executive Summary",
        "## Key Metrics",
        "## AI Adoption",
        "Posture: AI claimed, not evidenced",
        "## Thesis Fit",
        "## Indicative Valuation",
        "## Risk Overview",
        "## Contradictions & Cross-Document Checks",
        "## High Priority Findings",
        "## Findings by Category",
        "## Documents Reviewed",
        "## Limitations",
    ]:
        assert section in markdown
    assert "automated document triage" in markdown
    assert "not an appraisal" in markdown


def test_metrics_table_cites_sources():
    markdown = render_markdown(make_analysis())
    assert "| Arr | £9.6 million | FY2025 | `financials.pdf, p. 1` |" in markdown


def test_valuation_section_shows_range_and_assumptions():
    markdown = render_markdown(make_analysis())
    assert "£38.4m – £76.8m" in markdown
    assert "base £57.6m" in markdown
    assert "- Growth persists" in markdown
    assert "- Churn unknown" in markdown


def test_thesis_section_absent_without_thesis():
    markdown = render_markdown(make_analysis(thesis_fit=None))
    assert "## Thesis Fit" not in markdown


def test_valuation_absent_without_metrics():
    markdown = render_markdown(make_analysis(metrics=[], valuation=None))
    assert "## Indicative Valuation" not in markdown


def test_insufficient_data_message_with_metrics_but_no_valuation():
    markdown = render_markdown(make_analysis(valuation=None))
    assert "Insufficient financial data" in markdown


def test_write_outputs(tmp_path: Path):
    report_path, findings_path, deal_path = write_outputs(make_analysis(), tmp_path / "out")
    assert report_path.exists() and findings_path.exists() and deal_path.exists()
    findings = json.loads(findings_path.read_text())
    assert len(findings) == 2
    deal = json.loads(deal_path.read_text())
    assert deal["score"]["score"] == 72
    assert deal["valuation"]["value_base_millions"] == 57.6
