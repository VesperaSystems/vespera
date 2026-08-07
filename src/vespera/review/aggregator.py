"""Aggregate and deduplicate findings across chunks and documents."""

import re

from vespera.review.models import SEVERITY_ORDER, Finding


def _normalize(title: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", title.lower()).strip()


def _similar(a: str, b: str) -> bool:
    """Cheap fuzzy match: identical normalized titles, or high word overlap."""
    if a == b:
        return True
    words_a, words_b = set(a.split()), set(b.split())
    if not words_a or not words_b:
        return False
    overlap = len(words_a & words_b) / min(len(words_a), len(words_b))
    return overlap >= 0.8


def aggregate_findings(findings: list[Finding]) -> list[Finding]:
    """Collapse near-duplicate findings (same category + file + similar title).

    Keeps the highest-confidence instance. Result is sorted by severity then confidence.
    """
    kept: list[Finding] = []
    for finding in findings:
        duplicate_of = None
        for existing in kept:
            if (
                existing.category == finding.category
                and existing.source_file == finding.source_file
                and _similar(_normalize(existing.title), _normalize(finding.title))
            ):
                duplicate_of = existing
                break
        if duplicate_of is None:
            kept.append(finding)
        elif finding.confidence > duplicate_of.confidence:
            kept[kept.index(duplicate_of)] = finding

    kept.sort(key=lambda f: (SEVERITY_ORDER[f.severity], -f.confidence, f.source_file))
    return kept
