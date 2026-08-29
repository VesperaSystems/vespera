"""Render the Markdown deal report and JSON outputs."""

import json
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from vespera.review.models import CATEGORY_ORDER, SEVERITY_ORDER, Finding
from vespera.review.risks import RISK_DIMENSIONS, top_risks

if TYPE_CHECKING:
    from vespera.deal import DealAnalysis

DISCLAIMER = (
    "> **Important:** This report was produced by automated document triage. It is not "
    "legal, financial, or investment advice, and it does not replace review by qualified "
    "legal, financial, or other professional advisers. Any valuation figures are "
    "indicative screening ranges built on stated assumptions — they are not an appraisal "
    "or a recommendation to invest. Findings may be incomplete or incorrect and must be "
    "independently verified against the source documents."
)

LIMITATIONS = """\
- Analysis was performed by a local language model and may miss issues or misread context.
- Scanned or image-only documents are not analysed (no OCR in this version).
- Page references are approximate for findings that span page boundaries.
- Only documents in supported formats (PDF, DOCX, TXT, MD) were reviewed.
- Cross-document checks are based on extracted summaries, not full-text comparison.
- Metrics are extracted only where explicitly stated; nothing is estimated or derived.
- The indicative valuation is a multiples-based screening range resting entirely on the
  listed assumptions; it is not an appraisal and must not be relied on for any decision.\
"""

_CURRENCY_SYMBOL = {"GBP": "£", "USD": "$", "EUR": "€"}


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
        label = (
            "Evidence (verified quote)"
            if finding.evidence_verified
            else "Evidence (unverified — treat as inference, check the source)"
        )
        lines.append(f'  - {label}: "{finding.evidence.strip()}"')
    return "\n".join(lines)


def _cap(text: str) -> str:
    return text[0].upper() + text[1:] if text else text


def _score_section(analysis: "DealAnalysis") -> list[str]:
    score = analysis.score
    return [
        f"**Deal readiness: {score.score}/100 — {score.label}**",
        "",
        f"{score.rationale}",
        "",
    ]


def _metrics_section(analysis: "DealAnalysis") -> list[str]:
    if not analysis.metrics:
        return [
            "## Key Metrics",
            "",
            "No metrics found in financial-record documents (financial statements, "
            "investor updates, board minutes). Figures in plans, marketing, or "
            "third-party material are deliberately excluded from metrics.",
            "",
        ]
    parts = [
        "## Key Metrics",
        "",
        "*From financial-record documents only; figures in plans or marketing "
        "material are excluded.*",
        "",
        "| Metric | Value | Period | Source | Quote |",
        "| --- | --- | --- | --- | --- |",
    ]
    for m in analysis.metrics:
        source = m.source_file + (f", p. {m.source_page}" if m.source_page else "")
        value = m.value_text + (" (loss)" if m.amount < 0 else "")
        quote = "verified" if m.evidence_verified else "unverified"
        parts.append(f"| {_cap(m.name)} | {value} | {m.period} | `{source}` | {quote} |")
    parts.append("")
    return parts


def _thesis_section(analysis: "DealAnalysis") -> list[str]:
    fit = analysis.thesis_fit
    if fit is None:
        return []
    parts = [
        "## Thesis Fit",
        "",
        f"**Fit score: {fit.score}/100**",
        "",
    ]
    if fit.aligned:
        parts += ["Aligned with the thesis:", ""]
        parts += [f"- {p.point} *({p.evidence})*" for p in fit.aligned]
        parts.append("")
    if fit.conflicts:
        parts += ["Conflicts with the thesis:", ""]
        parts += [f"- {p.point} *({p.evidence})*" for p in fit.conflicts]
        parts.append("")
    if fit.unknowns:
        parts += ["No evidence either way:", ""]
        parts += [f"- {u}" for u in fit.unknowns]
        parts.append("")
    return parts


def _valuation_section(analysis: "DealAnalysis") -> list[str]:
    v = analysis.valuation
    if v is None:
        if analysis.metrics:
            return [
                "## Indicative Valuation",
                "",
                "Insufficient financial data for an indicative range (no explicitly "
                "stated revenue or ARR).",
                "",
            ]
        return []
    symbol = _CURRENCY_SYMBOL.get(v.currency, "")
    parts = [
        "## Indicative Valuation",
        "",
        f"**{symbol}{v.value_low_millions:.1f}m – {symbol}{v.value_high_millions:.1f}m** "
        f"(base {symbol}{v.value_base_millions:.1f}m) · "
        f"confidence {v.confidence:.0%}",
        "",
        f"Basis: {v.basis_metric.upper() if v.basis_metric == 'arr' else _cap(v.basis_metric)} "
        f"of {symbol}{v.basis_amount_millions:.1f}m × "
        f"{v.multiple_low:.1f}x / {v.multiple_base:.1f}x / {v.multiple_high:.1f}x "
        f"({v.sector}). Read as a screening range, not a point value.",
        "",
        "Assumptions behind the multiples:",
        "",
    ]
    parts += [f"- {a}" for a in v.assumptions]
    if v.caveats:
        parts += ["", "What would most change this range:", ""]
        parts += [f"- {c}" for c in v.caveats]
    parts.append("")
    return parts


def _cell(text: str, limit: int = 220) -> str:
    """Make model text safe for a Markdown table cell."""
    clean = " ".join(text.replace("|", "/").split()).lstrip(" .,;:")
    return clean[: limit - 1] + "…" if len(clean) > limit else clean


def _ai_section(analysis: "DealAnalysis") -> list[str]:
    profile = analysis.ai_profile
    if profile is None:
        return []
    parts = [
        "## AI Adoption",
        "",
        f"**Posture: {profile.posture}**",
        "",
        "| Aspect | Verdict | Detail | Evidence |",
        "| --- | --- | --- | --- |",
    ]
    for item in profile.aspects:
        parts.append(
            f"| {_cap(item.aspect)} | {item.verdict} "
            f"| {_cell(item.detail)} | {_cell(item.evidence, 120)} |"
        )
    parts += [
        "",
        f"Automation leverage: {_cell(profile.automation_leverage, 500)}",
        "",
        "AI-native, AI-augmented, and non-AI businesses carry different margin "
        "structures and headcount leverage; this profile is an input to the "
        "indicative valuation. \"Evidenced\" requires technical or contractual "
        "support — marketing language alone is reported as claimed-only.",
        "",
    ]
    return parts


def _risk_section(analysis: "DealAnalysis") -> list[str]:
    parts = [
        "## Risk Overview",
        "",
        "| Dimension | High | Medium | Low |",
        "| --- | --- | --- | --- |",
    ]
    for dim in RISK_DIMENSIONS:
        row = analysis.risk_matrix.get(dim, {})
        parts.append(
            f"| {_cap(dim)} | {row.get('high', 0)} | {row.get('medium', 0)} | {row.get('low', 0)} |"
        )
    parts.append("")
    risks = top_risks(analysis.findings)
    if risks:
        parts += ["Top risks:", ""]
        parts += [f"- **{f.title}** ({f.severity}) — {f.summary}" for f in risks]
        parts.append("")
    return parts


def _contradictions_section(analysis: "DealAnalysis") -> list[str]:
    cross = [
        f
        for f in analysis.findings
        if f.category
        in ("inconsistencies between documents", "missing documents explicitly referenced elsewhere")
    ]
    parts = ["## Contradictions & Cross-Document Checks", ""]
    if cross:
        parts += [_finding_line(f) for f in cross]
    else:
        parts.append("No cross-document contradictions or missing referenced documents detected.")
    parts.append("")
    return parts


def render_markdown(analysis: "DealAnalysis") -> str:
    findings = analysis.findings
    high_priority = [f for f in findings if f.severity in ("high", "medium")]
    counts = {s: sum(1 for f in findings if f.severity == s) for s in SEVERITY_ORDER}

    parts = [
        "# Vespera Deal Review",
        "",
        f"*Generated on {date.today().isoformat()} · All analysis performed locally*",
        "",
        DISCLAIMER,
        "",
    ]
    parts += _score_section(analysis)
    parts += [
        "## Executive Summary",
        "",
        f"Vespera reviewed **{len(analysis.documents)} documents** and recorded "
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
    if analysis.run and analysis.run.evidence_quotes_checked:
        parts.append(
            f"Evidence quotes mechanically verified against source documents: "
            f"**{analysis.run.evidence_quotes_verified} of "
            f"{analysis.run.evidence_quotes_checked}**. Quotes that could not be "
            "matched verbatim are labelled as inference below."
        )
        parts.append("")

    parts += _metrics_section(analysis)
    parts += _ai_section(analysis)
    parts += _thesis_section(analysis)
    parts += _valuation_section(analysis)
    parts += _risk_section(analysis)
    parts += _contradictions_section(analysis)

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
        parts += [f"### {_cap(category)} ({len(in_category)})", ""]
        parts += [_finding_line(f) for f in in_category]
        parts.append("")

    parts += ["## Documents Reviewed", ""]
    parts += [f"- `{name}`" for name in analysis.documents]
    if analysis.empty_documents:
        parts += ["", "Documents with no extractable text (possibly scanned images):"]
        parts += [f"- `{name}`" for name in analysis.empty_documents]
    if analysis.degraded_documents:
        parts += [
            "",
            "Documents where an analysis stage failed (results incomplete for these "
            "— review them manually or rerun):",
        ]
        parts += [f"- `{name}`" for name in analysis.degraded_documents]
    parts += ["", "## Limitations", "", LIMITATIONS, ""]
    if analysis.run:
        run = analysis.run
        parts += [
            "## Run Record",
            "",
            f"- Vespera version: {run.vespera_version}",
            f"- Model: {run.model} (local, via Ollama at {run.ollama_host})",
            f"- Generated: {run.timestamp}",
            f"- Thesis provided: {'yes' if run.thesis_provided else 'no'}",
            f"- Evidence quotes verified: {run.evidence_quotes_verified} of "
            f"{run.evidence_quotes_checked}",
            "",
            "The full machine-readable analysis, including this record, is in "
            "`deal.json` so any figure in this report can be traced later.",
            "",
        ]
    return "\n".join(parts)


def write_outputs(analysis: "DealAnalysis", output_dir: Path) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "report.md"
    findings_path = output_dir / "findings.json"
    deal_path = output_dir / "deal.json"
    report_path.write_text(render_markdown(analysis), encoding="utf-8")
    findings_path.write_text(
        json.dumps([f.model_dump() for f in analysis.findings], indent=2), encoding="utf-8"
    )
    deal_path.write_text(analysis.model_dump_json(indent=2), encoding="utf-8")
    return report_path, findings_path, deal_path
