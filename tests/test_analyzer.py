from pathlib import Path

from conftest import FakeProvider

from vespera.config import ReviewConfig
from vespera.documents.loader import Document, Page, load_document
from vespera.review.analyzer import analyze_document, chunk_document, cross_document_findings
from vespera.review.models import DocumentSummary, ExtractedFinding

EXTRACTED = ExtractedFinding(
    category="termination rights",
    title="Termination for convenience",
    summary="May terminate on notice.",
    severity="medium",
    evidence="terminated for convenience",
    confidence=0.9,
)


def test_chunk_document_tracks_pages():
    document = Document(
        path=Path("x.pdf"),
        pages=[Page(number=1, text="a" * 5000), Page(number=2, text="b" * 5000)],
    )
    chunks = chunk_document(document, chunk_chars=6000)
    assert len(chunks) == 2
    assert chunks[0].start_page == 1
    # second chunk starts mid-page-1 content but is stamped with the page it began on
    assert chunks[1].start_page in (1, 2)


def test_analyze_document_stamps_source(sample_pdf):
    provider = FakeProvider(chunk_findings=[EXTRACTED])
    document = load_document(sample_pdf)
    findings, summary = analyze_document(document, provider, ReviewConfig(), "contract.pdf")
    assert findings
    assert all(f.source_file == "contract.pdf" for f in findings)
    assert findings[0].source_page == 1
    assert summary is not None


def test_analyze_document_drops_info_level_missing_signatures(sample_pdf):
    noise = ExtractedFinding(
        category="missing signatures",
        title="Signatures present",
        summary="The document is fully executed.",
        severity="info",
        evidence="SIGNED for the Company",
        confidence=0.9,
    )
    noise_medium = ExtractedFinding(
        category="missing signatures",
        title="Signatures present",
        summary="Both parties have signed the agreement.",
        severity="medium",
        evidence="SIGNED for the Company",
        confidence=0.9,
    )
    real = ExtractedFinding(
        category="missing signatures",
        title="Blank signature block",
        summary="Signature areas are blank.",
        severity="medium",
        evidence="Signature: ____________",
        confidence=0.9,
    )
    provider = FakeProvider(chunk_findings=[noise, noise_medium, real])
    document = load_document(sample_pdf)
    findings, _ = analyze_document(document, provider, ReviewConfig(), "contract.pdf")
    assert [f.title for f in findings] == ["Blank signature block"] * len(findings)


def test_cross_document_findings_filters_categories():
    cross = [
        ExtractedFinding(
            category="missing documents explicitly referenced elsewhere",
            title="Schedule B missing",
            summary="MSA references Schedule B; not in dataroom.",
            severity="medium",
            evidence="Schedule B (Service Levels)",
            confidence=0.8,
        ),
        ExtractedFinding(  # out-of-scope category must be dropped
            category="governing law",
            title="English law",
            summary="n/a",
            severity="info",
            evidence="x",
            confidence=0.5,
        ),
    ]
    provider = FakeProvider(cross_findings=cross)
    summaries = {
        "a.pdf": DocumentSummary(contract_type="MSA", signed=True),
        "b.pdf": DocumentSummary(contract_type="NDA", signed=True),
    }
    result = cross_document_findings(summaries, provider, ReviewConfig())
    assert len(result) == 1
    assert result[0].source_file == "(multiple documents)"


def test_cross_document_skips_single_document():
    provider = FakeProvider()
    result = cross_document_findings(
        {"only.pdf": DocumentSummary(contract_type="NDA", signed=True)},
        provider,
        ReviewConfig(),
    )
    assert result == []
    assert provider.prompts == []
