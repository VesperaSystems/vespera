"""Tests for the deterministic deal-analysis stages."""

from vespera.review.metrics import dedupe_metrics, infer_unit, metric_conflicts
from vespera.review.models import Finding, KeyMetric
from vespera.review.risks import risk_matrix
from vespera.review.score import compute_score
from vespera.review.thesis import compute_fit_score


def make_finding(**overrides) -> Finding:
    base = dict(
        category="termination rights",
        title="Termination for convenience",
        summary="May terminate on notice.",
        severity="medium",
        source_file="msa.pdf",
        source_page=1,
        evidence="terminate",
        confidence=0.9,
    )
    base.update(overrides)
    return Finding(**base)


def make_metric(**overrides) -> KeyMetric:
    base = dict(
        name="arr",
        value_text="£9.6 million",
        amount=9.6,
        unit="GBP",
        period="FY2025",
        source_file="financials.pdf",
        source_page=1,
        evidence="ARR basis was £9.6 million",
    )
    base.update(overrides)
    return KeyMetric(**base)


class TestScore:
    def test_no_findings_is_strong(self):
        score, label = compute_score([])
        assert score == 95  # clamped
        assert label == "Strong reading"

    def test_high_findings_drag_score_down(self):
        findings = [make_finding(severity="high") for _ in range(3)]
        score, label = compute_score(findings)
        assert score == 70
        assert label == "Strong reading"

    def test_deductions_are_capped_per_severity(self):
        # 20 high findings deduct no more than the cap of 4 do
        few = compute_score([make_finding(severity="high") for _ in range(4)])[0]
        many = compute_score([make_finding(severity="high") for _ in range(20)])[0]
        assert few == many == 60

    def test_disclosure_findings_take_extra_deduction(self):
        base = [make_finding(severity="medium"), make_finding(severity="medium")]
        plain = compute_score(base)[0]
        disclosure = compute_score(
            base[:1] + [make_finding(severity="medium", category="missing signatures")]
        )[0]
        assert plain - disclosure == 4

    def test_info_findings_do_not_deduct(self):
        assert compute_score([make_finding(severity="info")])[0] == 95

    def test_verbose_risky_dataroom_reads_cautious_not_floor(self):
        findings = (
            [make_finding(severity="high") for _ in range(3)]
            + [make_finding(severity="medium") for _ in range(7)]
            + [make_finding(severity="low") for _ in range(18)]
            + [make_finding(severity="info") for _ in range(17)]
            + [
                make_finding(
                    severity="high", category="inconsistencies between documents"
                )
                for _ in range(3)
            ]
        )
        score, label = compute_score(findings)
        assert label == "Cautious reading"
        assert score > 5  # capped deductions keep it off the floor


class TestThesisScore:
    def test_balance_of_criteria(self):
        assert compute_fit_score(aligned=3, conflicts=5, unknowns=0) == 38
        assert compute_fit_score(aligned=5, conflicts=0, unknowns=0) == 100
        assert compute_fit_score(aligned=0, conflicts=4, unknowns=0) == 0

    def test_unknowns_reduce_conviction(self):
        assert compute_fit_score(3, 1, 2) == 69  # 75 - 6

    def test_nothing_assessed_is_midpoint(self):
        assert compute_fit_score(0, 0, 3) == 50


class TestUnitInference:
    def test_currency_signs_override_model_unit(self):
        assert infer_unit("£12.4 million", "months") == "GBP"
        assert infer_unit("$54.5M", "other") == "USD"
        assert infer_unit("€1.2m", "count") == "EUR"

    def test_percent_sign(self):
        assert infer_unit("117%", "other") == "percent"

    def test_fallback_kept_when_no_sign(self):
        assert infer_unit("86", "count") == "count"


class TestAmountFromText:
    def test_k_suffix(self):
        from vespera.review.metrics import amount_from_text

        assert amount_from_text("$500k") == 0.5
        assert amount_from_text("$300K") == 0.3

    def test_million_suffixes(self):
        from vespera.review.metrics import amount_from_text

        assert amount_from_text("£12.4 million") == 12.4
        assert amount_from_text("$1M") == 1.0
        assert amount_from_text("€2bn") == 2000.0

    def test_written_in_full(self):
        from vespera.review.metrics import amount_from_text

        assert amount_from_text("£54,500,000") == 54.5

    def test_bare_small_number_gives_no_scale(self):
        from vespera.review.metrics import amount_from_text

        assert amount_from_text("£850 per day") is None
        assert amount_from_text("86 customers") is None


class TestMetricGuards:
    def run_extraction(self, tmp_path, extracted):
        from conftest import FakeProvider

        from vespera.config import ReviewConfig
        from vespera.documents.loader import load_document
        from vespera.review.metrics import extract_metrics

        doc_path = tmp_path / "doc.txt"
        doc_path.write_text("Revenue and ARR figures are discussed in this document.")
        provider = FakeProvider(metrics=extracted)
        return extract_metrics(load_document(doc_path), provider, ReviewConfig(), "doc.txt")

    def test_targets_are_dropped(self, tmp_path):
        from vespera.review.models import ExtractedMetric

        target = ExtractedMetric(
            name="arr", value_text="$500k", amount=0.5, unit="USD",
            period="target Q4", evidence="ARR target $500k by year end",
        )
        assert self.run_extraction(tmp_path, [target]) == []

    def test_thousandfold_slip_corrected(self, tmp_path):
        from vespera.review.models import ExtractedMetric

        slipped = ExtractedMetric(
            name="arr", value_text="$500k", amount=500.0, unit="USD",
            period="FY2025", evidence="ARR reached $500k in FY2025",
        )
        metrics = self.run_extraction(tmp_path, [slipped])
        assert metrics[0].amount == 0.5

    def test_correct_amount_untouched(self, tmp_path):
        from vespera.review.models import ExtractedMetric

        good = ExtractedMetric(
            name="revenue", value_text="£12.4 million", amount=12.4, unit="GBP",
            period="FY2025", evidence="Total revenue for FY2025 was £12.4 million",
        )
        metrics = self.run_extraction(tmp_path, [good])
        assert metrics[0].amount == 12.4


class TestLossSign:
    def test_loss_in_evidence_flips_sign(self, tmp_path):
        from conftest import FakeProvider

        from vespera.config import ReviewConfig
        from vespera.documents.loader import load_document
        from vespera.review.metrics import extract_metrics
        from vespera.review.models import ExtractedMetric

        doc_path = tmp_path / "fin.txt"
        doc_path.write_text("Operating loss for FY2025 was £1.8 million.")
        provider = FakeProvider(
            metrics=[
                ExtractedMetric(
                    name="operating profit/loss",
                    value_text="£1.8 million",
                    amount=1.8,  # model forgot the sign
                    unit="GBP",
                    period="FY2025",
                    evidence="Operating loss for FY2025 was £1.8 million",
                )
            ]
        )
        metrics = extract_metrics(load_document(doc_path), provider, ReviewConfig(), "fin.txt")
        assert metrics[0].amount == -1.8


class TestRiskMatrix:
    def test_maps_categories_to_dimensions(self):
        findings = [
            make_finding(category="material liabilities", severity="high"),
            make_finding(category="exclusivity", severity="medium"),
            make_finding(category="missing signatures", severity="medium"),
            make_finding(category="governing law", severity="info"),  # excluded: context
            make_finding(category="termination rights", severity="info"),  # excluded: info
        ]
        matrix = risk_matrix(findings)
        assert matrix["financial"]["high"] == 1
        assert matrix["operational"]["medium"] == 1
        assert matrix["disclosure"]["medium"] == 1
        assert matrix["legal"] == {"high": 0, "medium": 0, "low": 0}


class TestMetricConflicts:
    def test_material_difference_becomes_high_finding(self):
        conflicts = metric_conflicts(
            [
                make_metric(amount=9.6, value_text="£9.6 million"),
                make_metric(amount=11.2, value_text="£11.2 million", source_file="update.txt"),
            ]
        )
        assert len(conflicts) == 1
        assert conflicts[0].category == "inconsistencies between documents"
        assert conflicts[0].severity == "high"  # ~17% apart
        assert "£9.6 million" in conflicts[0].summary
        assert "£11.2 million" in conflicts[0].summary

    def test_small_difference_tolerated(self):
        assert (
            metric_conflicts(
                [make_metric(amount=10.0), make_metric(amount=10.2, source_file="b.pdf")]
            )
            == []
        )

    def test_different_metrics_not_compared(self):
        assert (
            metric_conflicts(
                [make_metric(name="arr"), make_metric(name="revenue", source_file="b.pdf")]
            )
            == []
        )

    def test_dedupe_keeps_one_per_file_and_name(self):
        metrics = [make_metric(), make_metric(), make_metric(source_file="b.pdf")]
        assert len(dedupe_metrics(metrics)) == 2
