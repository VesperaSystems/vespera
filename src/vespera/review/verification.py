"""Mechanical evidence verification.

Every finding and metric quotes evidence, but the quote is written by the model. This
module checks, in plain code, whether the quote actually appears in the source
document. A quote that passes is marked verified; one that fails is labelled so the
reader treats it as inference rather than extraction. No model is involved in the
check.
"""

import re

from vespera.review.models import Finding, KeyMetric

MULTI_DOC_SOURCE = "(multiple documents)"

_QUOTE_CHARS = {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"}

_MIN_FRAGMENT_CHARS = 20
_MIN_WHOLE_CHARS = 12


def _normalize(text: str) -> str:
    for fancy, plain in _QUOTE_CHARS.items():
        text = text.replace(fancy, plain)
    return re.sub(r"\s+", " ", text.lower()).strip()


def _fragments(evidence: str) -> list[str]:
    """Split a quote into checkable pieces.

    Models often join two sources with 'vs', elide with '...', or wrap fragments in
    double quotes; each substantial piece must be found for the quote to count.
    """
    parts = re.split(r'\.\.\.|…|"|\s+vs\.?\s+', evidence)
    fragments = [p for p in parts if len(_normalize(p)) >= _MIN_FRAGMENT_CHARS]
    if fragments:
        return fragments
    if len(_normalize(evidence)) >= _MIN_WHOLE_CHARS:
        return [evidence]
    return []


def quote_appears(evidence: str, corpus_normalized: str) -> bool:
    fragments = _fragments(evidence)
    if not fragments:
        return False
    return all(_normalize(fragment) in corpus_normalized for fragment in fragments)


def verify_findings(findings: list[Finding], texts: dict[str, str]) -> tuple[int, int]:
    """Set evidence_verified on each finding. Returns (verified, checkable)."""
    normalized = {name: _normalize(text) for name, text in texts.items()}
    all_docs = " ".join(normalized.values())
    verified = checkable = 0
    for finding in findings:
        if not finding.evidence.strip():
            continue
        if finding.source_file == MULTI_DOC_SOURCE:
            corpus = all_docs
        else:
            corpus = normalized.get(finding.source_file)
            if corpus is None:
                continue
        checkable += 1
        finding.evidence_verified = quote_appears(finding.evidence, corpus)
        if finding.evidence_verified:
            verified += 1
    return verified, checkable


def verify_metrics(metrics: list[KeyMetric], texts: dict[str, str]) -> None:
    normalized = {name: _normalize(text) for name, text in texts.items()}
    for metric in metrics:
        corpus = normalized.get(metric.source_file)
        if corpus is None:
            continue
        metric.evidence_verified = quote_appears(metric.evidence, corpus)
