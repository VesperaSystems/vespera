"""Chunking and per-document / cross-document analysis."""

import re
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


# small local models like to report "signatures present" as a "missing signatures"
# finding despite instructions; a signature finding that affirms completeness is noise
_POSITIVE_SIGNATURE_NOTE = re.compile(
    r"signatures? (are |is )?present"
    r"|(is|are|been|was|were|parties)( duly| fully)? signed"
    r"|fully executed|duly executed"
    r"|signature (blocks?|areas?) (is|are) complete"
    r"|(both|all) parties (have |has )?signed",
    re.IGNORECASE,
)


def _is_noise(finding) -> bool:
    if finding.category != "missing signatures":
        return False
    if finding.severity == "info":
        return True
    return bool(_POSITIVE_SIGNATURE_NOTE.search(f"{finding.title} {finding.summary}"))


# cross-document "everything is fine" non-findings, same failure mode as above
_NON_FINDING = re.compile(
    r"\bno (documents? |other )?(is |are )?missing\b"
    r"|\bnot missing\b"
    r"|\bno (such )?(conflicts?|inconsistenc\w+|discrepanc\w+)\b"
    r"|\b(is|are) consistent\b"
    r"|\bno missing documents\b"
    r"|\breferences? no documents?\b"
    r"|\bno referenced documents?\b"
    r"|\bdoes not reference\b"
    r"|\bno references\b"
    r"|\bnot a missing document\b"
    r"|\bnot missing from the dataroom\b",
    re.IGNORECASE,
)


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
            if _is_noise(extracted):
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


def _render_summary(name: str, summary: DocumentSummary) -> str:
    """Compact rendering — small local models compare focused text far better than
    verbose JSON dumps."""
    lines = [f"### {name} ({summary.contract_type})"]
    if summary.parties:
        lines.append(f"Parties: {'; '.join(summary.parties)}")
    if summary.referenced_documents:
        lines.append(f"References these documents: {'; '.join(summary.referenced_documents)}")
    for fact in summary.key_facts:
        lines.append(f"- {fact}")
    return "\n".join(lines)


def cross_document_findings(
    summaries: dict[str, DocumentSummary],
    provider: LLMProvider,
    config: ReviewConfig,
) -> list[Finding]:
    """One pass over all document summaries to spot missing references and conflicts."""
    if len(summaries) < 2:
        return []
    file_list = "\n".join(f"- {name}" for name in summaries)
    rendered = "\n\n".join(_render_summary(name, s) for name, s in summaries.items())
    prompt = prompts.CROSS_DOCUMENT_PROMPT.format(
        role=prompts.ANALYST_ROLE, file_list=file_list, summaries=rendered
    )
    result = provider.generate_structured(prompt, CrossDocumentFindings)
    allowed = {"missing documents explicitly referenced elsewhere", "inconsistencies between documents"}
    findings = []
    for extracted in result.findings:
        if _NON_FINDING.search(f"{extracted.title} {extracted.summary}"):
            continue
        # this pass only asks for the two cross-document categories, but models often
        # label a conflict by its subject matter (e.g. "IP ownership / assignment");
        # re-categorize rather than silently dropping a genuine finding
        category = extracted.category
        if category not in allowed:
            text = f"{extracted.title} {extracted.summary}".lower()
            if "missing" in text or "not in the dataroom" in text:
                category = "missing documents explicitly referenced elsewhere"
            else:
                category = "inconsistencies between documents"
        findings.append(
            Finding(
                category=category,
                title=extracted.title,
                summary=extracted.summary,
                severity=extracted.severity,
                source_file="(multiple documents)",
                source_page=None,
                evidence=extracted.evidence[: config.max_evidence_chars],
                confidence=extracted.confidence,
            )
        )
    return findings
