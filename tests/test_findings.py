import pytest
from pydantic import ValidationError

from vespera.review.aggregator import aggregate_findings
from vespera.review.models import Finding


def make_finding(**overrides) -> Finding:
    base = dict(
        category="termination rights",
        title="Termination for convenience",
        summary="Client may terminate on 30 days notice.",
        severity="medium",
        source_file="msa.pdf",
        source_page=2,
        evidence="may terminate for convenience on thirty (30) days' notice",
        confidence=0.9,
    )
    base.update(overrides)
    return Finding(**base)


def test_finding_rejects_bad_severity():
    with pytest.raises(ValidationError):
        make_finding(severity="catastrophic")


def test_finding_rejects_out_of_range_confidence():
    with pytest.raises(ValidationError):
        make_finding(confidence=1.5)


def test_aggregator_collapses_duplicates_keeps_highest_confidence():
    low = make_finding(confidence=0.6)
    high = make_finding(confidence=0.95, summary="Better phrased duplicate.")
    other = make_finding(title="Change of control termination", category="change-of-control clauses")
    result = aggregate_findings([low, high, other])
    assert len(result) == 2
    dup = next(f for f in result if f.category == "termination rights")
    assert dup.confidence == 0.95


def test_aggregator_keeps_same_title_different_files():
    a = make_finding(source_file="a.pdf")
    b = make_finding(source_file="b.pdf")
    assert len(aggregate_findings([a, b])) == 2


def test_aggregator_sorts_by_severity():
    result = aggregate_findings(
        [
            make_finding(severity="info", title="Governing law"),
            make_finding(severity="high", title="Unlimited liability"),
            make_finding(severity="low", title="Notice period"),
        ]
    )
    assert [f.severity for f in result] == ["high", "low", "info"]
