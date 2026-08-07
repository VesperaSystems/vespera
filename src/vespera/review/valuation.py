"""Indicative comps-multiple valuation.

The model proposes multiples and states its assumptions; every calculation is done in
code. The output is an indicative screening range, never an appraisal.
"""

from vespera.llm.base import LLMProvider
from vespera.review.models import KeyMetric, MultipleProposal, ValuationResult
from vespera.review.prompts import ANALYST_ROLE

VALUATION_PROMPT = """\
{role}

Propose an indicative revenue-multiple band for screening this private company, based
only on the evidence below. You are NOT producing an appraisal — just a defensible
low/base/high multiple with every assumption stated.

Rules:
- Choose the basis: "arr" if ARR is available, otherwise "revenue".
- Multiples must satisfy low <= base <= high and reflect the company's sector, growth,
  margins, and retention as evidenced — nothing else.
- Private-market screening bands are wide: unless the evidence is unusually strong,
  low should be at least 25% below base and high at least 25% above base.
- List EVERY assumption you are making (sector norms, growth persistence, data gaps).
- "caveats": what would most change this band (e.g. contradictory figures, churn data).
- Be conservative when evidence is thin; reflect that in a lower confidence.

--- DEAL EVIDENCE ---
Sector/context: {context}

Key metrics:
{metrics}

Notable diligence flags:
{flags}
--- END DEAL EVIDENCE ---
"""

_BASIS_PREFERENCE = ["arr", "revenue"]
_MULTIPLE_BOUNDS = (0.1, 100.0)


def _pick_basis(metrics: list[KeyMetric]) -> KeyMetric | None:
    currency_units = {"GBP", "USD", "EUR"}
    for name in _BASIS_PREFERENCE:
        candidates = [m for m in metrics if m.name == name and m.unit in currency_units]
        if candidates:
            return candidates[0]
    return None


def indicative_valuation(
    metrics: list[KeyMetric],
    context: str,
    flags: list[str],
    provider: LLMProvider,
) -> ValuationResult | None:
    basis = _pick_basis(metrics)
    if basis is None:
        return None

    metrics_lines = "\n".join(
        f"- {m.name}: {m.value_text} ({m.period})"
        + (" [NEGATIVE — this is a loss]" if m.amount < 0 else "")
        for m in metrics
    )
    flags_lines = "\n".join(f"- {f}" for f in flags) or "- none"
    prompt = VALUATION_PROMPT.format(
        role=ANALYST_ROLE, context=context or "unknown", metrics=metrics_lines, flags=flags_lines
    )
    proposal = provider.generate_structured(prompt, MultipleProposal)

    lo, hi = _MULTIPLE_BOUNDS
    low, base, high = sorted(
        min(max(m, lo), hi)
        for m in (proposal.multiple_low, proposal.multiple_base, proposal.multiple_high)
    )
    return ValuationResult(
        basis_metric=basis.name,
        basis_amount_millions=basis.amount,
        currency=basis.unit,
        multiple_low=low,
        multiple_base=base,
        multiple_high=high,
        value_low_millions=round(basis.amount * low, 1),
        value_base_millions=round(basis.amount * base, 1),
        value_high_millions=round(basis.amount * high, 1),
        sector=proposal.sector,
        assumptions=proposal.assumptions,
        confidence=proposal.confidence,
        caveats=proposal.caveats,
    )
