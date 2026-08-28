"""Fast triage: the three most decisive items before committing to a full review.

One quick summary pass per document, one synthesis call. No chunk-level analysis, no
deep cross-document check, no valuation — minutes instead of an hour, so the human
can decide whether the full review is worth running at all. The output is about
whether deeper review is warranted; it is never investment advice.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from vespera.config import ReviewConfig
from vespera.documents.loader import discover_documents, load_document
from vespera.llm.base import LLMProvider
from vespera.review import prompts
from vespera.review.models import DocumentSummary, TriageResult

TRIAGE_PROMPT = """\
{role}

Below are summaries of every document in a dataroom, produced as a fast first pass
before a full document-level review. From these summaries alone, identify EXACTLY
THREE items that are most decisive for whether this deal deserves a full review:
the strongest reasons to stop now (deal-breakers), the issues that must be resolved
(concerns), or the facts that most strengthen the case (strengths). Pick the three
most decisive overall, whatever their direction.

Rules:
- Only use what the summaries support; name the source document for each item.
- "missing_essentials": essential documents or facts a reviewer would expect and the
  dataroom does not contain (e.g. historical financials, signed key contracts).
- The verdict is about whether a FULL REVIEW is warranted — never about whether to
  invest. Missing essentials alone do not make a deal-breaker; they belong in
  missing_essentials and may justify "resolve the flagged items" instead.
{thesis_block}
--- DOCUMENT SUMMARIES ---
{summaries}
--- END SUMMARIES ---
"""

THESIS_BLOCK = """
The investor's criteria, for judging what is decisive:
--- INVESTMENT CRITERIA ---
{thesis}
--- END CRITERIA ---
"""


@dataclass
class TriageOutcome:
    result: TriageResult
    documents: list[str]
    empty_documents: list[str]
    degraded_documents: list[str]


def triage_dataroom(
    path: Path,
    thesis_path: Path | None = None,
    provider: LLMProvider | None = None,
    config: ReviewConfig | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> TriageOutcome:
    from vespera.llm.ollama import OllamaProvider

    config = config or ReviewConfig()
    provider = provider or OllamaProvider(model=config.model, host=config.ollama_host)
    notify = on_progress or (lambda stage: None)

    summaries: dict[str, DocumentSummary] = {}
    reviewed: list[str] = []
    empty: list[str] = []
    degraded: list[str] = []

    for doc_path in discover_documents(path):
        relative_name = str(doc_path.relative_to(path))
        notify(f"Reading {relative_name}")
        document = load_document(doc_path)
        if document.is_empty:
            empty.append(relative_name)
            continue
        prompt = prompts.SUMMARY_PROMPT.format(
            role=prompts.ANALYST_ROLE,
            source_file=relative_name,
            document_text=document.text[: config.chunk_chars],
        )
        try:
            summaries[relative_name] = provider.generate_structured(prompt, DocumentSummary)
        except Exception:
            degraded.append(f"{relative_name} (summary failed)")
        reviewed.append(relative_name)

    notify("Synthesising triage")
    summary_lines = []
    for name, summary in summaries.items():
        facts = "; ".join(summary.key_facts[:8]) or summary.contract_type
        signed = "signed" if summary.signed else "NOT signed/unclear"
        summary_lines.append(f"- {name} ({summary.contract_type}, {signed}): {facts}")

    thesis_block = ""
    if thesis_path is not None:
        thesis_block = THESIS_BLOCK.format(thesis=thesis_path.read_text(encoding="utf-8")[:6000])

    result = provider.generate_structured(
        TRIAGE_PROMPT.format(
            role=prompts.ANALYST_ROLE,
            thesis_block=thesis_block,
            summaries="\n".join(summary_lines) or "- no readable documents",
        ),
        TriageResult,
    )
    return TriageOutcome(
        result=result, documents=reviewed, empty_documents=empty, degraded_documents=degraded
    )
