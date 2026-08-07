import json
from pathlib import Path

from vespera.review.models import Finding
from vespera.review.report import render_markdown, write_outputs

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


def test_report_contains_required_sections():
    markdown = render_markdown(FINDINGS, ["msa.pdf", "nda.txt"])
    for section in [
        "# Vespera Due Diligence Review",
        "## Executive Summary",
        "## High Priority Findings",
        "## Findings by Category",
        "## Documents Reviewed",
        "## Limitations",
    ]:
        assert section in markdown
    assert "not" in markdown and "legal" in markdown  # disclaimer present
    assert "automated document triage" in markdown
    assert "msa.pdf, p. 1" in markdown
    assert "`nda.txt`" in markdown


def test_report_counts():
    markdown = render_markdown(FINDINGS, ["msa.pdf"])
    assert "**2 findings**" in markdown
    assert "1 high" in markdown


def test_write_outputs(tmp_path: Path):
    report_path, findings_path = write_outputs(FINDINGS, ["msa.pdf"], tmp_path / "out")
    assert report_path.exists() and findings_path.exists()
    data = json.loads(findings_path.read_text())
    assert len(data) == 2
    assert data[0]["category"] == "change-of-control clauses"
    assert data[0]["source_page"] == 1
