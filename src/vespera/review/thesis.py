"""Score the deal against the user's investment thesis."""

from vespera.llm.base import LLMProvider
from vespera.review.models import (
    Finding,
    KeyMetric,
    ThesisAssessment,
    ThesisFit,
    ThesisPoint,
)
from vespera.review.prompts import ANALYST_ROLE

THESIS_PROMPT = """\
{role}

Below is an investor's written investment thesis, followed by what a document review
of a deal's dataroom found. Go through the thesis criterion by criterion and assess
each one against the evidence.

Rules:
- Output exactly ONE assessment per thesis criterion. Do not skip any criterion and
  do not invent criteria that are not in the thesis.
- verdict "aligned": the dataroom evidence supports the criterion.
  verdict "conflict": the evidence contradicts it.
  verdict "unknown": the dataroom gives no evidence either way.
- "evidence" must cite the document or metric behind the verdict ('none' for unknown).
- Do not recommend investing or not investing; assess fit only.

--- INVESTMENT THESIS ---
{thesis}
--- END THESIS ---

--- DEAL EVIDENCE ---
Key metrics:
{metrics}

Key findings from the document review:
{findings}
--- END DEAL EVIDENCE ---
"""


def compute_fit_score(aligned: int, conflicts: int, unknowns: int) -> int:
    """Deterministic fit score from the balance of assessed criteria.

    Small local models report the verdicts reliably but not a number, so the
    number is computed here.
    """
    assessed = aligned + conflicts
    if assessed == 0:
        return 50  # nothing assessable either way
    score = round(100 * aligned / assessed)
    score -= 3 * unknowns  # unassessed criteria reduce conviction
    return max(0, min(100, score))


def assess_thesis_fit(
    thesis_text: str,
    metrics: list[KeyMetric],
    findings: list[Finding],
    provider: LLMProvider,
) -> ThesisFit:
    metrics_lines = "\n".join(
        f"- {m.name}: {m.value_text} ({m.period}) [source: {m.source_file}]"
        + (" [NEGATIVE — this is a loss]" if m.amount < 0 else "")
        for m in metrics
    ) or "- none extracted"
    findings_lines = "\n".join(
        f"- [{f.severity}] {f.title}: {f.summary} [source: {f.source_file}]"
        for f in findings[:20]
    ) or "- none"
    prompt = THESIS_PROMPT.format(
        role=ANALYST_ROLE,
        thesis=thesis_text.strip()[:6000],
        metrics=metrics_lines,
        findings=findings_lines,
    )
    assessment = provider.generate_structured(prompt, ThesisAssessment)

    seen: set[tuple[str, str]] = set()
    aligned: list[ThesisPoint] = []
    conflicts: list[ThesisPoint] = []
    unknowns: list[str] = []
    for item in assessment.assessments:
        key = (item.criterion.strip().lower(), item.verdict)
        if key in seen:
            continue
        seen.add(key)
        if item.verdict == "aligned":
            aligned.append(ThesisPoint(point=item.criterion, evidence=item.evidence))
        elif item.verdict == "conflict":
            conflicts.append(ThesisPoint(point=item.criterion, evidence=item.evidence))
        else:
            unknowns.append(item.criterion)

    # a criterion assessed either way cannot simultaneously be unknown
    assessed_points = {p.point.strip().lower() for p in aligned + conflicts}
    unknowns = [u for u in unknowns if u.strip().lower() not in assessed_points]

    return ThesisFit(
        score=compute_fit_score(len(aligned), len(conflicts), len(unknowns)),
        aligned=aligned,
        conflicts=conflicts,
        unknowns=unknowns,
    )
