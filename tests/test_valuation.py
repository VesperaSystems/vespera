from vespera.review.models import KeyMetric, MultipleProposal
from vespera.review.valuation import indicative_valuation


class MultipleProvider:
    def __init__(self, proposal: MultipleProposal):
        self.proposal = proposal

    def generate_structured(self, prompt, schema):
        assert schema is MultipleProposal
        return self.proposal


def make_metric(name="arr", amount=9.6, unit="GBP") -> KeyMetric:
    return KeyMetric(
        name=name,
        value_text=f"£{amount}m",
        amount=amount,
        unit=unit,
        period="FY2025",
        source_file="financials.pdf",
        source_page=1,
        evidence="x",
    )


PROPOSAL = MultipleProposal(
    basis="arr",
    multiple_low=4.0,
    multiple_base=6.0,
    multiple_high=8.0,
    sector="B2B robotics software",
    assumptions=["Growth persists at ~40%"],
    confidence=0.6,
    caveats=["Churn data unavailable"],
)


def test_arithmetic_is_done_in_code():
    result = indicative_valuation([make_metric()], "robotics", [], MultipleProvider(PROPOSAL))
    assert result.value_low_millions == 38.4
    assert result.value_base_millions == 57.6
    assert result.value_high_millions == 76.8
    assert result.currency == "GBP"
    assert result.assumptions == ["Growth persists at ~40%"]


def test_prefers_arr_over_revenue():
    metrics = [make_metric(name="revenue", amount=12.4), make_metric(name="arr", amount=9.6)]
    result = indicative_valuation(metrics, "x", [], MultipleProvider(PROPOSAL))
    assert result.basis_metric == "arr"
    assert result.basis_amount_millions == 9.6


def test_no_currency_basis_returns_none():
    metrics = [make_metric(name="net revenue retention", amount=117, unit="percent")]
    assert indicative_valuation(metrics, "x", [], MultipleProvider(PROPOSAL)) is None


def test_disordered_multiples_are_sorted():
    scrambled = PROPOSAL.model_copy(
        update={"multiple_low": 8.0, "multiple_base": 4.0, "multiple_high": 6.0}
    )
    result = indicative_valuation([make_metric()], "x", [], MultipleProvider(scrambled))
    assert result.multiple_low <= result.multiple_base <= result.multiple_high
