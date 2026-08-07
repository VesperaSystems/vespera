"""Render the Markdown report and findings JSON."""

import json
from datetime import date
from pathlib import Path

from vespera.review.models import CATEGORY_ORDER, SEVERITY_ORDER, Finding

DISCLAIMER = (
    "> **Important:** This report was produced by automated document triage. It is not "
    "legal, financial, or investment advice, and it does not replace review by qualified "
    "legal, financial, or other professional advisers. Findings may be incomplete or "
    "incorrect and must be independently verified against the source documents."
)

LIMITATIONS = """\
- Analysis was performed by a local language model and may miss issues or misread context.
- Scanned or image-only documents are not analysed (no OCR in this version).
- Page references are approximate for findings that span page boundaries.
- Only documents in supported formats (PDF, DOCX, TXT, MD) were reviewed.
- Cross-document checks are based on extracted summaries, not full-text comparison.\
"""


def _finding_line(finding: Finding) -> str:
    location = finding.source_file
    if finding.source_page:
        location += f", p. {finding.source_page}"
    lines = [
        f"- **{finding.title}** — severity: {finding.severity}, "
        f"confidence: {finding.confidence:.0%}",
        f"  - {finding.summary}",
        f"  - Source: `{location}`",
    ]
    if finding.evidence.strip():
        lines.append(f'  - Evidence: "{finding.evidence.strip()}"')
    return "\n".join(lines)


def render_markdown(
    findings: list[Finding],
    documents: list[str],
    empty_documents: list[str] | None = None,
) -> str:
    high_priority = [f for f in findings if f.severity in ("high", "medium")]
    counts = {s: sum(1 for f in findings if f.severity == s) for s in SEVERITY_ORDER}

    parts = [
        "# Vespera Due Diligence Review",
        "",
        f"*Generated on {date.today().isoformat()} · All analysis performed locally*",
        "",
        DISCLAIMER,
        "",
        "## Executive Summary",
        "",
        f"Vespera reviewed **{len(documents)} documents** and recorded "
        f"**{len(findings)} findings**: {counts['high']} high, {counts['medium']} medium, "
        f"{counts['low']} low severity, and {counts['info']} informational.",
        "",
    ]
    if high_priority:
        parts.append(
            "Items flagged for priority attention: "
            + "; ".join(f.title for f in high_priority[:6])
            + "."
        )
        parts.append("")

    parts += ["## High Priority Findings", ""]
    if high_priority:
        parts += [_finding_line(f) for f in high_priority]
    else:
        parts.append("No high or medium severity findings were recorded.")
    parts.append("")

    parts += ["## Findings by Category", ""]
    for category in CATEGORY_ORDER:
        in_category = [f for f in findings if f.category == category]
        if not in_category:
            continue
        parts += [f"### {category[0].upper() + category[1:]} ({len(in_category)})", ""]
        parts += [_finding_line(f) for f in in_category]
        parts.append("")

    parts += ["## Documents Reviewed", ""]
    parts += [f"- `{name}`" for name in documents]
    if empty_documents:
        parts += ["", "Documents with no extractable text (possibly scanned images):"]
        parts += [f"- `{name}`" for name in empty_documents]
    parts += ["", "## Limitations", "", LIMITATIONS, ""]
    return "\n".join(parts)


def write_outputs(
    findings: list[Finding],
    documents: list[str],
    output_dir: Path,
    empty_documents: list[str] | None = None,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "report.md"
    findings_path = output_dir / "findings.json"
    report_path.write_text(render_markdown(findings, documents, empty_documents), encoding="utf-8")
    findings_path.write_text(
        json.dumps([f.model_dump() for f in findings], indent=2), encoding="utf-8"
    )
    return report_path, findings_path
