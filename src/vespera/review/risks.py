"""Deterministic risk matrix: finding categories mapped to risk dimensions."""

from vespera.review.models import Finding

RISK_DIMENSIONS = ["financial", "legal", "operational", "disclosure"]

CATEGORY_DIMENSION = {
    "material liabilities": "financial",
    "termination rights": "legal",
    "change-of-control clauses": "legal",
    "assignment restrictions": "legal",
    "IP ownership / assignment": "legal",
    "confidentiality obligations": "legal",
    "exclusivity": "operational",
    "unusual obligations": "operational",
    "potential red flags": "operational",
    "missing signatures": "disclosure",
    "missing documents explicitly referenced elsewhere": "disclosure",
    "inconsistencies between documents": "disclosure",
    # parties / dates / contract type / governing law are informational context
}


def risk_matrix(findings: list[Finding]) -> dict[str, dict[str, int]]:
    """Counts of non-informational findings per dimension and severity."""
    matrix = {dim: {"high": 0, "medium": 0, "low": 0} for dim in RISK_DIMENSIONS}
    for finding in findings:
        dimension = CATEGORY_DIMENSION.get(finding.category)
        if dimension is None or finding.severity == "info":
            continue
        matrix[dimension][finding.severity] += 1
    return matrix


def top_risks(findings: list[Finding], limit: int = 5) -> list[Finding]:
    """Highest-severity, in-scope findings for the risk narrative."""
    in_scope = [
        f
        for f in findings
        if f.severity != "info" and CATEGORY_DIMENSION.get(f.category) is not None
    ]
    return in_scope[:limit]  # findings arrive sorted by severity then confidence
