"""Key financial metric extraction and cross-document conflict detection."""

import re

from vespera.config import ReviewConfig
from vespera.documents.loader import Document
from vespera.llm.base import LLMProvider
from vespera.review.models import ExtractedMetrics, Finding, KeyMetric
from vespera.review.prompts import ANALYST_ROLE

# company metrics may only come from documents that record them, never from documents
# that merely mention numbers (plans, testimonials, competitor analyses)
METRIC_SOURCE_KINDS = {
    "financial statements or management accounts",
    "investor update",
    "board minutes",
}

# cheap gate so we only spend an LLM call on documents with financial content
FINANCIAL_HINT = re.compile(
    r"revenue|\bARR\b|\bMRR\b|EBITDA|gross margin|net revenue retention|\bNRR\b"
    r"|cash balance|runway|churn|[£$€]\s?\d",
    re.IGNORECASE,
)

METRICS_PROMPT = """\
{role}

Extract the financial metrics that are EXPLICITLY stated in this document excerpt.

Rules:
- Only extract values written in the text. Never estimate, derive, or fill gaps.
- Only ACTUAL, historical values. Never extract targets, forecasts, projections,
  goals, or plans — "ARR target $500k" and "projected revenue" are not metrics.
- At most ONE value per metric: the most recent stated. Skip monthly or quarterly
  breakdowns and tables of period-by-period values. Twenty metrics maximum.
- Empty list is a valid answer if no metrics are stated.
- "amount": for currency metrics give the amount in MILLIONS (£54,500,000 -> 54.5);
  for percentages give the percent number (57% -> 57); for counts give the number.
- Losses and negative values must have a NEGATIVE amount: an operating loss of
  £1.8 million -> amount -1.8.
- "value_text" is the value exactly as written.
- "evidence" is a short verbatim excerpt containing the value.

Document: {source_file}

--- DOCUMENT TEXT START ---
{text}
--- DOCUMENT TEXT END ---
"""

# sanity bounds per unit-ish class; out-of-range extractions are discarded
_AMOUNT_BOUNDS = {"percent": (0, 500), "count": (0, 10_000_000), "months": (0, 240)}
_CURRENCY_BOUNDS = (0.001, 100_000)  # millions

_CURRENCY_SIGNS = {"£": "GBP", "$": "USD", "€": "EUR"}

# aspirational numbers are not metrics; the prompt forbids them, this enforces it
_TARGET_HINT = re.compile(
    r"\btargets?\b|\bforecasts?\b|\bproject(ed|ion|ions)\b|\bgoals?\b"
    r"|\bexpected\b|\bplann?(ed|s)?\b|\baim(s|ed|ing)?\b|\bambition\b",
    re.IGNORECASE,
)

_VALUE_PATTERN = re.compile(
    r"([£$€])\s*([\d][\d,]*\.?\d*)\s*(k|thousand|m|mm|mn|million|bn|b|billion)?\b",
    re.IGNORECASE,
)

_SUFFIX_TO_MILLIONS = {
    "k": 0.001, "thousand": 0.001,
    "m": 1.0, "mm": 1.0, "mn": 1.0, "million": 1.0,
    "bn": 1000.0, "b": 1000.0, "billion": 1000.0,
}


def amount_from_text(value_text: str) -> float | None:
    """Best-effort re-derivation of a currency amount in millions from the verbatim
    value, used to catch thousand-fold unit slips like "$500k" recorded as 500."""
    match = _VALUE_PATTERN.search(value_text.replace(",", ""))
    if match is None:
        return None
    number = float(match.group(2))
    suffix = (match.group(3) or "").lower()
    if suffix:
        return number * _SUFFIX_TO_MILLIONS[suffix]
    if number >= 100_000:  # written out in full, e.g. £54,500,000
        return number / 1_000_000
    return None  # a bare small number gives no confident scale


def infer_unit(value_text: str, fallback: str) -> str:
    """Derive the unit from the verbatim value; small models mislabel units."""
    for sign, code in _CURRENCY_SIGNS.items():
        if sign in value_text:
            return code
    if "%" in value_text:
        return "percent"
    return fallback


def has_financial_content(document: Document) -> bool:
    return bool(FINANCIAL_HINT.search(document.text))


def extract_metrics(
    document: Document,
    provider: LLMProvider,
    config: ReviewConfig,
    relative_name: str,
) -> list[KeyMetric]:
    prompt = METRICS_PROMPT.format(
        role=ANALYST_ROLE,
        source_file=relative_name,
        text=document.text[: config.chunk_chars],
    )
    result = provider.generate_structured(prompt, ExtractedMetrics)
    first_page = document.pages[0].number if document.pages else None
    metrics = []
    for extracted in result.metrics:
        if _TARGET_HINT.search(f"{extracted.value_text} {extracted.period} {extracted.evidence}"):
            continue
        unit = infer_unit(extracted.value_text, extracted.unit)
        if unit in _CURRENCY_SIGNS.values():
            derived = amount_from_text(extracted.value_text)
            if derived is not None and extracted.amount > 0:
                ratio = extracted.amount / derived
                if ratio > 3 or ratio < 1 / 3:
                    extracted.amount = derived  # trust the written value over the model
        low, high = _AMOUNT_BOUNDS.get(unit, _CURRENCY_BOUNDS)
        if not (low <= abs(extracted.amount) <= high):
            continue
        # losses stated in prose ("operating loss was £1.8 million") often come back
        # with a positive amount; fix the sign deterministically
        if extracted.amount > 0 and re.search(r"\bloss\b", extracted.evidence, re.IGNORECASE):
            extracted.amount = -extracted.amount
        metrics.append(
            KeyMetric(
                name=extracted.name,
                value_text=extracted.value_text,
                amount=extracted.amount,
                unit=unit,
                period=extracted.period,
                source_file=relative_name,
                source_page=first_page,
                evidence=extracted.evidence[: config.max_evidence_chars],
            )
        )
    return metrics


def metric_conflicts(metrics: list[KeyMetric], tolerance: float = 0.05) -> list[Finding]:
    """Deterministically flag the same metric reported with materially different values."""
    by_name: dict[str, list[KeyMetric]] = {}
    for metric in metrics:
        by_name.setdefault(metric.name, []).append(metric)

    findings = []
    for name, group in by_name.items():
        if len(group) < 2:
            continue
        baseline = group[0]
        for other in group[1:]:
            if baseline.amount == 0:
                continue
            relative_diff = abs(other.amount - baseline.amount) / abs(baseline.amount)
            if relative_diff <= tolerance:
                continue
            findings.append(
                Finding(
                    category="inconsistencies between documents",
                    title=f"Conflicting {name} figures across documents",
                    summary=(
                        f"{baseline.source_file} states {name} as {baseline.value_text} "
                        f"({baseline.period}), but {other.source_file} states "
                        f"{other.value_text} ({other.period}) — a "
                        f"{relative_diff:.0%} difference."
                    ),
                    severity="high" if relative_diff > 0.15 else "medium",
                    source_file="(multiple documents)",
                    source_page=None,
                    evidence=f'{baseline.source_file}: "{baseline.evidence}" vs '
                    f'{other.source_file}: "{other.evidence}"',
                    confidence=0.95,
                )
            )
    return findings


def dedupe_metrics(metrics: list[KeyMetric]) -> list[KeyMetric]:
    """One row per (name, source_file); keeps the first occurrence."""
    seen = set()
    kept = []
    for metric in metrics:
        key = (metric.name, metric.source_file)
        if key in seen:
            continue
        seen.add(key)
        kept.append(metric)
    return kept
