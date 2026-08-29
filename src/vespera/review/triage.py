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
from vespera.review.models import (
    CriteriaChecks,
    CriterionCheck,
    DocumentSummary,
    TriageItem,
    TriageResult,
)

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
- FIRST check for kill-criteria: if the investor's criteria name conditions under
  which they pass on a deal, test each one against the summaries. A violated
  pass-condition, or two documents contradicting each other on one, is always more
  decisive than a strength and MUST take one of the three slots.
- Do not fill all three slots with strengths unless nothing negative or contradictory
  exists in the summaries at all.
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


CRITERIA_CHECK_PROMPT = """\
{role}

Below are an investor's criteria and summaries of every document in a dataroom.
Go through the criteria one by one and check each against the summaries. Include
every criterion — especially any conditions under which the investor passes on a
deal ("we pass on...", "we avoid...", deal-breakers).

Statuses:
- "met": the summaries support the criterion.
- "violated": the summaries contradict it, or a stated pass-condition applies.
- "contradicted-evidence": two documents disagree about the fact the criterion
  depends on.
- "unknown": the summaries give no evidence either way.

--- INVESTMENT CRITERIA ---
{thesis}
--- END CRITERIA ---

--- DOCUMENT SUMMARIES ---
{summaries}
--- END SUMMARIES ---
"""


def apply_criteria_checks(result: TriageResult, checks: list[CriterionCheck]) -> TriageResult:
    """A violated pass-condition must occupy a triage slot; enforced in code because
    small models bury kill-criteria under strengths."""
    problems = [c for c in checks if c.status in ("violated", "contradicted-evidence")]
    if not problems:
        return result
    covered = " ".join(f"{i.title} {i.why}".lower() for i in result.items)
    missing = [
        c for c in problems
        if not any(word in covered for word in c.criterion.lower().split() if len(word) > 5)
    ]
    items = list(result.items)
    for check in missing:
        strength_positions = [i for i, item in enumerate(items) if item.direction == "strength"]
        if not strength_positions:
            break
        label = "deal-breaker" if check.status == "violated" else "concern"
        items[strength_positions[-1]] = TriageItem(
            title=f"Criteria check failed: {check.criterion}",
            direction=label,
            why=(
                "The investor's criteria treat this as a condition to pass on, and the "
                "document summaries indicate it applies."
                if check.status == "violated"
                else "Documents disagree about the fact this criterion depends on."
            ),
            source=check.evidence,
        )
    if any(item.direction == "deal-breaker" for item in items):
        verdict = "significant deal-breakers evident"
        rationale = (
            "One or more of the investor's stated pass-conditions appears to apply; "
            "see the criteria check."
        )
    elif any(item.direction == "concern" for item in items):
        verdict = "resolve the flagged items before a full review"
        rationale = result.rationale
    else:
        verdict = result.verdict
        rationale = result.rationale
    return TriageResult(
        items=items,
        missing_essentials=result.missing_essentials,
        verdict=verdict,
        rationale=rationale,
    )


@dataclass
class TriageOutcome:
    result: TriageResult
    documents: list[str]
    empty_documents: list[str]
    degraded_documents: list[str]
    criteria_checks: list[CriterionCheck] | None = None


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

    summaries_text = "\n".join(summary_lines) or "- no readable documents"
    result = provider.generate_structured(
        TRIAGE_PROMPT.format(
            role=prompts.ANALYST_ROLE,
            thesis_block=thesis_block,
            summaries=summaries_text,
        ),
        TriageResult,
    )

    checks: list[CriterionCheck] | None = None
    if thesis_path is not None:
        notify("Checking investor criteria")
        try:
            checked = provider.generate_structured(
                CRITERIA_CHECK_PROMPT.format(
                    role=prompts.ANALYST_ROLE,
                    thesis=thesis_path.read_text(encoding="utf-8")[:6000],
                    summaries=summaries_text,
                ),
                CriteriaChecks,
            )
            checks = checked.checks
            result = apply_criteria_checks(result, checks)
        except Exception:
            degraded.append("(criteria check failed)")

    return TriageOutcome(
        result=result,
        documents=reviewed,
        empty_documents=empty,
        degraded_documents=degraded,
        criteria_checks=checks,
    )
