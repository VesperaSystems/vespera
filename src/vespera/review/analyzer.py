"""Chunking and per-document / cross-document analysis."""

import json
from dataclasses import dataclass

from vespera.config import ReviewConfig
from vespera.documents.loader import Document
from vespera.llm.base import LLMProvider
from vespera.review import prompts
from vespera.review.models import (
    ChunkFindings,
    CrossDocumentFindings,
    DocumentSummary,
    Finding,
)


@dataclass
class Chunk:
    text: str
    start_page: int | None


def chunk_document(document: Document, chunk_chars: int, overlap_chars: int = 0) -> list[Chunk]:
    """Split a document into chunks, keeping track of the page each chunk starts on."""
    chunks: list[Chunk] = []
    current_text = ""
    current_page: int | None = None

    for page in document.pages:
        remaining = page.text
        while remaining:
            if not current_text:
                current_page = page.number
            space = chunk_chars - len(current_text)
            current_text += remaining[:space]
            remaining = remaining[space:]
            if len(current_text) >= chunk_chars:
                chunks.append(Chunk(text=current_text, start_page=current_page))
                # carry a small overlap so clauses split across a boundary aren't lost
                current_text = current_text[-overlap_chars:] if overlap_chars else ""
    if current_text.strip():
        chunks.append(Chunk(text=current_text, start_page=current_page))
    return chunks


def analyze_document(
    document: Document,
    provider: LLMProvider,
    config: ReviewConfig,
    relative_name: str,
) -> tuple[list[Finding], DocumentSummary | None]:
    """Extract findings from one document, plus a summary for the cross-document pass."""
    findings: list[Finding] = []
    for chunk in chunk_document(document, config.chunk_chars, config.chunk_overlap_chars):
        page_info = f"Page: {chunk.start_page}" if chunk.start_page else "Page: not applicable"
        prompt = prompts.CHUNK_PROMPT.format(
            role=prompts.ANALYST_ROLE,
            source_file=relative_name,
            page_info=page_info,
            chunk_text=chunk.text,
        )
        result = provider.generate_structured(prompt, ChunkFindings)
        for extracted in result.findings:
            # small local models like to report "signatures present" as an info-level
            # "missing signatures" finding despite instructions; a real missing
            # signature is always medium/high per the prompt's severity guide
            if extracted.category == "missing signatures" and extracted.severity == "info":
                continue
            findings.append(
                Finding(
                    category=extracted.category,
                    title=extracted.title,
                    summary=extracted.summary,
                    severity=extracted.severity,
                    source_file=relative_name,
                    source_page=chunk.start_page,
                    evidence=extracted.evidence[: config.max_evidence_chars],
                    confidence=extracted.confidence,
                )
            )

    summary: DocumentSummary | None = None
    summary_prompt = prompts.SUMMARY_PROMPT.format(
        role=prompts.ANALYST_ROLE,
        source_file=relative_name,
        document_text=document.text[: config.chunk_chars],
    )
    try:
        summary = provider.generate_structured(summary_prompt, DocumentSummary)
    except Exception:
        summary = None  # the cross-document pass is best-effort
    return findings, summary


def cross_document_findings(
    summaries: dict[str, DocumentSummary],
    provider: LLMProvider,
    config: ReviewConfig,
) -> list[Finding]:
    """One pass over all document summaries to spot missing references and conflicts."""
    if len(summaries) < 2:
        return []
    file_list = "\n".join(f"- {name}" for name in summaries)
    rendered = "\n".join(
        f"### {name}\n{json.dumps(summary.model_dump(), indent=2)}"
        for name, summary in summaries.items()
    )
    prompt = prompts.CROSS_DOCUMENT_PROMPT.format(
        role=prompts.ANALYST_ROLE, file_list=file_list, summaries=rendered
    )
    result = provider.generate_structured(prompt, CrossDocumentFindings)
    allowed = {"missing documents explicitly referenced elsewhere", "inconsistencies between documents"}
    return [
        Finding(
            category=extracted.category,
            title=extracted.title,
            summary=extracted.summary,
            severity=extracted.severity,
            source_file="(multiple documents)",
            source_page=None,
            evidence=extracted.evidence[: config.max_evidence_chars],
            confidence=extracted.confidence,
        )
        for extracted in result.findings
        if extracted.category in allowed
    ]
