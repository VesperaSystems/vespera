"""End-to-end analyze_dataroom with an injected fake provider (no Ollama)."""

from pathlib import Path

from conftest import FakeProvider

from vespera.config import ReviewConfig
from vespera.deal import analyze_dataroom
from vespera.review.models import ExtractedFinding, ExtractedMetric


def build_dataroom(tmp_path: Path) -> Path:
    room = tmp_path / "room"
    room.mkdir()
    (room / "financials.txt").write_text(
        "FY2025 revenue was £12.4 million. ARR reached £9.6 million."
    )
    (room / "update.txt").write_text("ARR has now reached £11.2 million.")
    (room / "note.txt").write_text("General meeting note with no numbers.")
    return room


FINDING = ExtractedFinding(
    category="termination rights",
    title="Termination for convenience",
    summary="May terminate on notice.",
    severity="medium",
    evidence="terminate",
    confidence=0.9,
)


class MetricsByDocProvider(FakeProvider):
    """Returns different metrics depending on which document is in the prompt."""

    def generate_structured(self, prompt, schema):
        from vespera.review.models import ExtractedMetrics

        if schema is ExtractedMetrics:
            self.prompts.append(prompt)
            if "financials.txt" in prompt:
                return ExtractedMetrics(
                    metrics=[
                        ExtractedMetric(
                            name="arr",
                            value_text="£9.6 million",
                            amount=9.6,
                            unit="GBP",
                            period="FY2025",
                            evidence="ARR reached £9.6 million",
                        )
                    ]
                )
            return ExtractedMetrics(
                metrics=[
                    ExtractedMetric(
                        name="arr",
                        value_text="£11.2 million",
                        amount=11.2,
                        unit="GBP",
                        period="Oct 2025",
                        evidence="ARR has now reached £11.2 million",
                    )
                ]
            )
        return super().generate_structured(prompt, schema)


def test_analyze_dataroom_end_to_end(tmp_path: Path):
    room = build_dataroom(tmp_path)
    thesis = tmp_path / "thesis.md"
    thesis.write_text("We invest in ARR > £5m businesses.")

    provider = MetricsByDocProvider(chunk_findings=[FINDING])
    analysis = analyze_dataroom(
        room,
        thesis_path=thesis,
        provider=provider,
        deep_provider=provider,
        config=ReviewConfig(),
    )

    assert len(analysis.documents) == 3
    # metrics extracted only from the two docs that pass the financial gate
    assert {m.source_file for m in analysis.metrics} == {"financials.txt", "update.txt"}
    # the conflicting ARR figures became a high-severity contradiction
    conflict = next(
        f for f in analysis.findings if f.category == "inconsistencies between documents"
    )
    assert conflict.severity == "high"
    assert 0 <= analysis.score.score <= 100
    assert analysis.thesis_fit is not None
    assert analysis.valuation is not None
    assert analysis.valuation.basis_metric == "arr"


def test_analyze_dataroom_without_thesis(tmp_path: Path):
    room = build_dataroom(tmp_path)
    provider = MetricsByDocProvider(chunk_findings=[])
    analysis = analyze_dataroom(room, provider=provider, deep_provider=provider)
    assert analysis.thesis_fit is None
