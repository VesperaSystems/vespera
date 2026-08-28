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


def test_repair_truncated_json():
    from pydantic import BaseModel

    from vespera.llm.ollama import _repair_truncated_json

    class Item(BaseModel):
        name: str

    class Items(BaseModel):
        metrics: list[Item]

    truncated = '{\n  "metrics": [\n    {"name": "revenue"},\n    {"name": "gross margi'
    repaired = None
    for candidate in _repair_truncated_json(truncated):
        try:
            repaired = Items.model_validate_json(candidate)
            break
        except Exception:
            continue
    assert repaired is not None
    assert [i.name for i in repaired.metrics] == ["revenue"]


def test_degraded_document_does_not_abort_run(tmp_path):
    from conftest import FakeProvider

    from vespera.deal import analyze_dataroom
    from vespera.llm.ollama import OllamaError
    from vespera.review.models import ExtractedMetrics

    room = tmp_path / "room"
    room.mkdir()
    (room / "good.txt").write_text("A plain note with no numbers.")
    (room / "bad-metrics.txt").write_text("Revenue was £5 million this year.")

    class FailingMetricsProvider(FakeProvider):
        def generate_structured(self, prompt, schema):
            if schema is ExtractedMetrics:
                raise OllamaError("model returned output that failed validation twice")
            return super().generate_structured(prompt, schema)

    provider = FailingMetricsProvider()
    analysis = analyze_dataroom(room, provider=provider, deep_provider=provider)
    assert len(analysis.documents) == 2  # the run completed
    assert analysis.degraded_documents == ["bad-metrics.txt (metrics extraction failed)"]


def test_verify_metrics():
    good = KeyMetric(
        name="revenue", value_text="£1m", amount=1.0, unit="GBP", period="FY25",
        source_file="msa.pdf", source_page=1,
        evidence="terminate immediately on written notice if the other party",
    )
    bad = good.model_copy(update={"evidence": "revenue was fourteen million pounds"})
    verify_metrics([good, bad], {"msa.pdf": DOC})
    assert good.evidence_verified and not bad.evidence_verified
