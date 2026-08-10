"""Tests for the deterministic AI-adoption logic."""

from vespera.review.ai_adoption import (
    ai_claim_findings,
    derive_posture,
    enforce_evidence_standard,
)
from vespera.review.models import AIAspectAssessment, AIAssessment, AIProfile


def aspect(aspect: str, verdict: str) -> AIAspectAssessment:
    return AIAspectAssessment(
        aspect=aspect, verdict=verdict, detail="detail", evidence="doc.pdf"
    )


def assessment(*aspects: AIAspectAssessment) -> AIAssessment:
    return AIAssessment(aspects=list(aspects), automation_leverage="x")


class TestPosture:
    def test_evidenced_product_is_ai_native(self):
        posture, product = derive_posture(
            assessment(aspect("product", "evidenced"), aspect("operations", "absent"))
        )
        assert posture == "AI-native product"
        assert product == "evidenced"

    def test_claimed_only_product_is_flagged_posture(self):
        posture, product = derive_posture(assessment(aspect("product", "claimed-only")))
        assert posture == "AI claimed, not evidenced"
        assert product == "claimed-only"

    def test_operations_only_is_augmented(self):
        posture, _ = derive_posture(
            assessment(aspect("product", "absent"), aspect("operations", "evidenced"))
        )
        assert posture == "AI-augmented operations"

    def test_all_absent_is_no_ai(self):
        posture, _ = derive_posture(
            assessment(
                aspect("product", "absent"),
                aspect("operations", "absent"),
                aspect("engineering", "absent"),
            )
        )
        assert posture == "No meaningful AI deployment"

    def test_no_coverage_is_unclear(self):
        posture, _ = derive_posture(assessment(aspect("product", "unclear")))
        assert posture == "AI posture unclear"


class TestClaimFindings:
    def make_profile(self, *aspects) -> AIProfile:
        return AIProfile(
            posture="x", product_ai="x", aspects=list(aspects), automation_leverage="x"
        )

    def test_claimed_only_becomes_red_flag(self):
        profile = self.make_profile(aspect("product", "claimed-only"))
        findings = ai_claim_findings(profile)
        assert len(findings) == 1
        assert findings[0].category == "potential red flags"
        assert findings[0].severity == "medium"
        assert "product" in findings[0].title

    def test_evidenced_and_absent_produce_no_flags(self):
        profile = self.make_profile(
            aspect("product", "evidenced"), aspect("operations", "absent")
        )
        assert ai_claim_findings(profile) == []

    def test_non_product_claims_do_not_flag(self):
        profile = self.make_profile(aspect("operations", "claimed-only"))
        assert ai_claim_findings(profile) == []


class TestEvidenceStandard:
    def test_marketing_only_excerpt_downgrades_evidenced_to_claimed(self):
        result = enforce_evidence_standard(
            assessment(aspect("product", "evidenced"), aspect("operations", "evidenced")),
            {"09.pdf": "Our AI-powered platform raises a ticket when a reading exceeds the configured threshold."},
        )
        assert all(a.verdict == "claimed-only" for a in result.aspects)
        assert "[downgraded" in result.aspects[0].detail

    def test_concrete_marker_keeps_evidenced(self):
        result = enforce_evidence_standard(
            assessment(aspect("product", "evidenced")),
            {"09.pdf": "The anomaly detection model is trained on 400M sensor readings and served via GPU inference."},
        )
        assert result.aspects[0].verdict == "evidenced"

    def test_no_ai_language_downgrades_to_unclear(self):
        result = enforce_evidence_standard(
            assessment(aspect("engineering", "evidenced")),
            {"03.pdf": "The Contractor shall design and implement the firmware."},
        )
        assert result.aspects[0].verdict == "unclear"

    def test_no_excerpts_keeps_model_judgment(self):
        result = enforce_evidence_standard(assessment(aspect("product", "evidenced")), {})
        assert result.aspects[0].verdict == "evidenced"
