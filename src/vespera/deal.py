"""Deal analysis: the library API behind `vespera review`.

    from vespera.deal import analyze_dataroom
    analysis = analyze_dataroom(Path("./dataroom"), thesis_path=Path("thesis.md"))

Everything runs locally; `analysis` is a single pydantic object you can serialize,
render, or post-process.
"""

from pathlib import Path
from typing import Callable

from pydantic import BaseModel

from vespera.config import ReviewConfig
from vespera.documents.loader import discover_documents, load_document
from vespera.llm.base import LLMProvider
from vespera.llm.ollama import OllamaProvider
from vespera.review.aggregator import aggregate_findings
from vespera.review.analyzer import analyze_document, cross_document_findings
from vespera.review.metrics import (
    dedupe_metrics,
    extract_metrics,
    has_financial_content,
    metric_conflicts,
)
from vespera.review.models import (
    DocumentSummary,
    Finding,
    KeyMetric,
    ReadinessScore,
    ThesisFit,
    ValuationResult,
)
from vespera.review.risks import risk_matrix
from vespera.review.score import score_deal
from vespera.review.thesis import assess_thesis_fit
from vespera.review.valuation import indicative_valuation


class DealAnalysis(BaseModel):
    documents: list[str]
    empty_documents: list[str]
    metrics: list[KeyMetric]
    findings: list[Finding]
    risk_matrix: dict[str, dict[str, int]]
    score: ReadinessScore
    thesis_fit: ThesisFit | None
    valuation: ValuationResult | None


def analyze_dataroom(
    path: Path,
    thesis_path: Path | None = None,
    provider: LLMProvider | None = None,
    deep_provider: LLMProvider | None = None,
    config: ReviewConfig | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> DealAnalysis:
    """Run the full local deal analysis over a dataroom directory."""
    config = config or ReviewConfig()
    provider = provider or OllamaProvider(model=config.model, host=config.ollama_host)
    # comparing documents needs deeper reasoning than clause extraction, so the
    # cross-document pass defaults to the model's thinking mode
    deep_provider = deep_provider or OllamaProvider(
        model=config.model, host=config.ollama_host, think=True
    )
    notify = on_progress or (lambda stage: None)

    paths = discover_documents(path)
    findings: list[Finding] = []
    metrics: list[KeyMetric] = []
    summaries: dict[str, DocumentSummary] = {}
    reviewed: list[str] = []
    empty: list[str] = []

    for doc_path in paths:
        relative_name = str(doc_path.relative_to(path))
        notify(f"Analysing {relative_name}")
        document = load_document(doc_path)
        if document.is_empty:
            empty.append(relative_name)
            continue
        doc_findings, summary = analyze_document(document, provider, config, relative_name)
        findings.extend(doc_findings)
        if summary is not None:
            summaries[relative_name] = summary
        if has_financial_content(document):
            notify(f"Extracting metrics from {relative_name}")
            metrics.extend(extract_metrics(document, provider, config, relative_name))
        reviewed.append(relative_name)

    notify("Cross-referencing documents (deep check)")
    findings.extend(cross_document_findings(summaries, deep_provider, config))

    metrics = dedupe_metrics(metrics)
    findings.extend(metric_conflicts(metrics))
    findings = aggregate_findings(findings)

    notify("Scoring the deal")
    score = score_deal(findings, provider)
    matrix = risk_matrix(findings)

    thesis_fit = None
    if thesis_path is not None:
        notify("Assessing thesis fit")
        thesis_fit = assess_thesis_fit(
            thesis_path.read_text(encoding="utf-8"), metrics, findings, provider
        )

    valuation = None
    if metrics:
        notify("Building indicative valuation")
        context_facts = [fact for s in summaries.values() for fact in s.key_facts[:2]]
        context = "; ".join(context_facts[:8]) or "unknown"
        top_flags = [f"{f.title} ({f.severity})" for f in findings[:6]]
        valuation = indicative_valuation(metrics, context, top_flags, provider)

    return DealAnalysis(
        documents=reviewed,
        empty_documents=empty,
        metrics=metrics,
        findings=findings,
        risk_matrix=matrix,
        score=score,
        thesis_fit=thesis_fit,
        valuation=valuation,
    )
