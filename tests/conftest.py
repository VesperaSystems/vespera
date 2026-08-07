from pathlib import Path

import pymupdf
import pytest

from vespera.review.models import ChunkFindings, CrossDocumentFindings, DocumentSummary


class FakeProvider:
    """LLMProvider stand-in that returns canned responses, no network."""

    def __init__(self, chunk_findings=None, summary=None, cross_findings=None):
        self.chunk_findings = chunk_findings or []
        self.summary = summary
        self.cross_findings = cross_findings or []
        self.prompts: list[str] = []

    def generate_structured(self, prompt, schema):
        self.prompts.append(prompt)
        if schema is ChunkFindings:
            return ChunkFindings(findings=self.chunk_findings)
        if schema is DocumentSummary:
            if self.summary is None:
                return DocumentSummary(contract_type="unknown", signed=False)
            return self.summary
        if schema is CrossDocumentFindings:
            return CrossDocumentFindings(findings=self.cross_findings)
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
