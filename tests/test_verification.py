"""Tests for mechanical evidence-quote verification."""

from vespera.review.models import Finding, KeyMetric
from vespera.review.verification import quote_appears, verify_findings, verify_metrics

DOC = """MASTER SERVICES AGREEMENT

3. TERMINATION. Northgate may terminate this Agreement for convenience at any
time on thirty (30) days' written notice. Either party may terminate immediately
on written notice if the other party commits a material breach.
"""


def make_finding(evidence: str, source_file: str = "msa.pdf", **overrides) -> Finding:
    base = dict(
        category="termination rights",
        title="Termination for convenience",
        summary="x",
        severity="medium",
        source_file=source_file,
        source_page=1,
        evidence=evidence,
        confidence=0.9,
    )
    base.update(overrides)
    return Finding(**base)


def _norm(text: str) -> str:
    from vespera.review.verification import _normalize

    return _normalize(text)


class TestQuoteAppears:
    def test_exact_quote_across_line_breaks(self):
        quote = "Northgate may terminate this Agreement for convenience at any time on thirty (30) days' written notice."
        assert quote_appears(quote, _norm(DOC))

    def test_fabricated_quote_fails(self):
        assert not quote_appears(
            "The supplier guarantees a 99.9% uptime service level.", _norm(DOC)
        )

    def test_elided_quote_verifies_each_fragment(self):
        quote = "Northgate may terminate this Agreement for convenience... commits a material breach"
        assert quote_appears(quote, _norm(DOC))

    def test_elided_quote_with_one_fake_fragment_fails(self):
        quote = "Northgate may terminate this Agreement for convenience... uptime of 99.9% is guaranteed here"
        assert not quote_appears(quote, _norm(DOC))

    def test_curly_quotes_normalized(self):
        quote = "thirty (30) days’ written notice"
        assert quote_appears(quote, _norm(DOC))

    def test_tiny_evidence_not_verifiable(self):
        assert not quote_appears("30", _norm(DOC))


class TestVerifyFindings:
    def test_marks_verified_and_unverified(self):
        real = make_finding("Northgate may terminate this Agreement for convenience at any time")
        fake = make_finding("The moon is made of cheese and the contract says so plainly.")
        verified, checkable = verify_findings([real, fake], {"msa.pdf": DOC})
        assert (verified, checkable) == (1, 2)
        assert real.evidence_verified and not fake.evidence_verified

    def test_multi_document_findings_check_all_texts(self):
        finding = make_finding(
            '"Northgate may terminate this Agreement for convenience at any time" vs "The board approved the supply agreement at the October meeting"',
            source_file="(multiple documents)",
        )
        texts = {
            "msa.pdf": DOC,
            "minutes.docx": "The board approved the supply agreement at the October meeting.",
        }
        verify_findings([finding], texts)
        assert finding.evidence_verified

    def test_unknown_source_is_skipped(self):
        finding = make_finding("anything at all in this quote", source_file="ghost.pdf")
        verified, checkable = verify_findings([finding], {"msa.pdf": DOC})
        assert (verified, checkable) == (0, 0)
        assert not finding.evidence_verified


def test_verify_metrics():
    good = KeyMetric(
        name="revenue", value_text="£1m", amount=1.0, unit="GBP", period="FY25",
        source_file="msa.pdf", source_page=1,
        evidence="terminate immediately on written notice if the other party",
    )
    bad = good.model_copy(update={"evidence": "revenue was fourteen million pounds"})
    verify_metrics([good, bad], {"msa.pdf": DOC})
    assert good.evidence_verified and not bad.evidence_verified
