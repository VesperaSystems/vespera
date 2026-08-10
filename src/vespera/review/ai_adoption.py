"""AI adoption assessment: does the business actually use AI, or just claim to?

AI-native, AI-augmented, and non-AI businesses carry different margin structures and
headcount leverage, so the profile feeds the indicative valuation. The model assesses
where AI appears in the evidence; the posture classification — and the red flag when
AI is claimed but nothing technical supports it — are derived deterministically.
"""

import re

from vespera.documents.loader import Document
from vespera.llm.base import LLMProvider
from vespera.review.models import (
    AIAssessment,
    AIProfile,
    DocumentSummary,
    Finding,
)
from vespera.review.prompts import ANALYST_ROLE

AI_PROMPT = """\
{role}

Assess where AI actually appears in this company's business, using only the dataroom
evidence below. Distinguish hard evidence (models, ML infrastructure, agentic
workflows, named AI systems doing real work, AI engineering roles or contracts) from
marketing or investor-deck language that merely claims AI.

Output exactly one assessment per aspect:
- "product": is AI/ML/LLM part of what the company sells?
- "operations": is AI used to run the business (support, sales, content, internal
  tooling)?
- "engineering": does the team demonstrably build with or maintain AI (roles,
  contracts, infrastructure, development practices)?

Rules:
- "evidenced" requires concrete technical or contractual support, not adjectives.
  The litmus test: does any document name a model, an ML technique, training data,
  an AI vendor or API, inference/GPU infrastructure, or an AI-specific role or
  contract? If nothing like that appears, the verdict CANNOT be "evidenced".
- Calling something "AI-powered", "intelligent", or "self-optimising" is marketing,
  not evidence. If the same document describes the actual mechanism and it is
  rule-based, threshold-based, or manual, the verdict is "claimed-only" — the claim
  and the mechanism contradict each other.
- If documents cover the area and show no AI at all, use "absent"; if the dataroom
  simply doesn't speak to it, use "unclear".

Example: a product sheet says "our AI-powered maintenance platform" but explains that
alerts fire "when a reading exceeds the configured threshold" — that is a rule-based
system with an AI label, so product = "claimed-only".

--- DATAROOM EVIDENCE ---
Document summaries:
{summaries}

Raw excerpts from documents that mention AI/ML (read the mechanism, not the label):
{excerpts}

Key findings:
{findings}
--- END EVIDENCE ---
"""

AI_HINT = re.compile(
    r"\bAI\b|artificial intelligence|machine[- ]learning|\bML\b|\bLLM\b|deep learning"
    r"|neural network|\bagentic\b|self-optimi[sz]ing",
    re.IGNORECASE,
)

# concrete technical markers that real AI usage descriptions contain and marketing
# labels don't; "evidenced" verdicts are checked against these in code
CONCRETE_AI = re.compile(
    r"\bmodel(s)?\b|\btrain(ing|ed)\b|\binference\b|\bneural\b|\btransformer\b"
    r"|\bLLM\b|\bGPT\b|\bfine-?tun|\bdataset\b|\bembedding|\bGPU\b|\bclassifier\b"
    r"|\banomaly detection\b|\bregression\b|\bcomputer vision\b|\bNLP\b"
    r"|\bOpenAI\b|\bAnthropic\b|\bClaude\b|\bollama\b|\bhugging ?face\b",
    re.IGNORECASE,
)


def ai_excerpt(document: Document, window: int = 900) -> str | None:
    """A raw-text window around the first AI mention, so the assessor sees the
    mechanism description and not just a summarised label."""
    match = AI_HINT.search(document.text)
    if match is None:
        return None
    start = max(0, match.start() - window // 3)
    return document.text[start : start + window].strip()

POSTURE_LABELS = {
    "ai-native": "AI-native product",
    "ai-claimed": "AI claimed, not evidenced",
    "ai-augmented": "AI-augmented operations",
    "no-ai": "No meaningful AI deployment",
    "unclear": "AI posture unclear",
}


def enforce_evidence_standard(
    assessment: AIAssessment, excerpts: dict[str, str] | None
) -> AIAssessment:
    """Downgrade 'evidenced' verdicts the raw text cannot support.

    The litmus test from the prompt, enforced deterministically: if none of the
    AI-mentioning excerpts contain a concrete technical marker, nothing in this
    dataroom evidences AI — at best it claims it.
    """
    if not excerpts:
        return assessment  # nothing to check against; keep the model's judgment
    corpus = "\n".join(excerpts.values())
    if CONCRETE_AI.search(corpus):
        return assessment
    downgraded_to = "claimed-only" if AI_HINT.search(corpus) else "unclear"
    for item in assessment.aspects:
        if item.verdict == "evidenced":
            item.verdict = downgraded_to
            item.detail += (
                " [downgraded: no concrete technical AI marker found in the documents]"
            )
    return assessment


def derive_posture(assessment: AIAssessment) -> tuple[str, str]:
    """Deterministic posture from per-aspect verdicts. Returns (posture, product_ai)."""
    verdicts = {}
    for item in assessment.aspects:
        verdicts.setdefault(item.aspect, item.verdict)  # first assessment per aspect wins
    product = verdicts.get("product", "unclear")
    others_evidenced = any(
        verdicts.get(a) == "evidenced" for a in ("operations", "engineering")
    )
    if product == "evidenced":
        posture = "ai-native"
    elif product == "claimed-only":
        posture = "ai-claimed"
    elif others_evidenced:
        posture = "ai-augmented"
    elif all(verdicts.get(a) == "absent" for a in ("product", "operations", "engineering")):
        posture = "no-ai"
    else:
        posture = "unclear"
    return POSTURE_LABELS[posture], product


def ai_claim_findings(profile: AIProfile) -> list[Finding]:
    """AI asserted without technical support is a diligence red flag in its own right.

    Only the product aspect generates a finding — that is where AI-washing changes
    the economics a buyer is paying for; the full profile is in the report anyway.
    """
    findings = []
    for item in profile.aspects:
        if item.verdict != "claimed-only" or item.aspect != "product":
            continue
        findings.append(
            Finding(
                category="potential red flags",
                title=f"AI claims about {item.aspect} lack supporting evidence",
                summary=(
                    f"The dataroom asserts AI in the {item.aspect} area ({item.detail}) "
                    "but no technical, contractual, or operational document substantiates "
                    "it. AI-dependent economics should not be assumed in valuation."
                ),
                severity="medium",
                source_file="(multiple documents)",
                source_page=None,
                evidence=item.evidence[:300],
                confidence=0.85,
            )
        )
    return findings


def assess_ai_adoption(
    summaries: dict[str, DocumentSummary],
    findings: list[Finding],
    provider: LLMProvider,
    excerpts: dict[str, str] | None = None,
) -> AIProfile:
    summary_lines = []
    for name, summary in summaries.items():
        facts = "; ".join(summary.key_facts[:6]) or summary.contract_type
        summary_lines.append(f"- {name}: {facts}")
    excerpt_lines = "\n\n".join(
        f"### {name}\n{text}" for name, text in (excerpts or {}).items()
    ) or "- none"
    findings_lines = "\n".join(
        f"- [{f.severity}] {f.title}: {f.summary}" for f in findings[:15]
    ) or "- none"
    prompt = AI_PROMPT.format(
        role=ANALYST_ROLE,
        summaries="\n".join(summary_lines) or "- none",
        excerpts=excerpt_lines,
        findings=findings_lines,
    )
    assessment = provider.generate_structured(prompt, AIAssessment)
    assessment = enforce_evidence_standard(assessment, excerpts)
    posture, product_ai = derive_posture(assessment)
    return AIProfile(
        posture=posture,
        product_ai=product_ai,
        aspects=assessment.aspects,
        automation_leverage=assessment.automation_leverage,
    )
