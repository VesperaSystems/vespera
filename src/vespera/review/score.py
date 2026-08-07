"""Deterministic deal-readiness score.

The score is computed in code so it is reproducible and testable; the LLM only
writes the one-sentence rationale.
"""

from vespera.llm.base import LLMProvider
from vespera.review.models import Finding, ReadinessScore, ScoreRationale

DISCLOSURE_CATEGORIES = {
    "missing signatures",
    "missing documents explicitly referenced elsewhere",
    "inconsistencies between documents",
}

# per-finding deduction and how many findings of that class can count — capping stops
# a verbose model's long tail of minor findings from flooring the score
SEVERITY_DEDUCTION = {"high": (10, 4), "medium": (3, 8), "low": (1, 6), "info": (0, 0)}
DISCLOSURE_EXTRA = (4, 4)

STRONG_THRESHOLD = 70
BALANCED_THRESHOLD = 40


def compute_score(findings: list[Finding]) -> tuple[int, str]:
    score = 100
    counted: dict[str, int] = {}
    disclosure_counted = 0
    for finding in findings:
        deduction, cap = SEVERITY_DEDUCTION[finding.severity]
        if counted.get(finding.severity, 0) < cap:
            score -= deduction
            counted[finding.severity] = counted.get(finding.severity, 0) + 1
        extra, extra_cap = DISCLOSURE_EXTRA
        if finding.category in DISCLOSURE_CATEGORIES and disclosure_counted < extra_cap:
            score -= extra
            disclosure_counted += 1
    score = max(5, min(95, score))
    if score >= STRONG_THRESHOLD:
        label = "Strong reading"
    elif score >= BALANCED_THRESHOLD:
        label = "Balanced reading"
    else:
        label = "Cautious reading"
    return score, label


RATIONALE_PROMPT = """\
You are a cautious due diligence analyst. In ONE sentence (under 25 words), weigh the
favourable signals against the flagged risks for this deal. Be factual and neutral —
no recommendation to invest or not invest.

Deal readiness score: {score}/100 ({label})
Top findings:
{top_findings}
"""


def score_deal(findings: list[Finding], provider: LLMProvider | None) -> ReadinessScore:
    score, label = compute_score(findings)
    rationale = f"{len(findings)} findings recorded; see risk overview and findings below."
    if provider is not None:
        top = "\n".join(
            f"- [{f.severity}] {f.title}: {f.summary}" for f in findings[:8]
        ) or "- none"
        try:
            result = provider.generate_structured(
                RATIONALE_PROMPT.format(score=score, label=label, top_findings=top),
                ScoreRationale,
            )
            rationale = result.rationale.strip()
        except Exception:
            pass  # the deterministic fallback rationale is fine
    return ReadinessScore(score=score, label=label, rationale=rationale)
