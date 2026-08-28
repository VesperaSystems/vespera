"""Deal analysis: the library API behind `vespera review`.

    from vespera.deal import analyze_dataroom
    analysis = analyze_dataroom(Path("./dataroom"), thesis_path=Path("thesis.md"))

Everything runs locally; `analysis` is a single pydantic object you can serialize,
render, or post-process.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from pydantic import BaseModel

import vespera

from vespera.config import ReviewConfig
from vespera.documents.loader import discover_documents, load_document
from vespera.llm.base import LLMProvider
from vespera.llm.ollama import OllamaProvider
from vespera.review.aggregator import aggregate_findings
from vespera.review.ai_adoption import ai_claim_findings, ai_excerpt, assess_ai_adoption
from vespera.review.analyzer import analyze_document, cross_document_findings
from vespera.review.metrics import (
    dedupe_metrics,
    extract_metrics,
    has_financial_content,
    metric_conflicts,
)
from vespera.review.models import (
    AIProfile,
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
from vespera.review.verification import verify_findings, verify_metrics


class RunRecord(BaseModel):
    """How this analysis was produced, so any answer can be explained later."""

    vespera_version: str
    model: str
    ollama_host: str
    timestamp: str
    chunk_chars: int
    thesis_provided: bool
    evidence_quotes_verified: int
    evidence_quotes_checked: int


class DealAnalysis(BaseModel):
    documents: list[str]
    empty_documents: list[str]
    degraded_documents: list[str] = []
    metrics: list[KeyMetric]
    findings: list[Finding]
    risk_matrix: dict[str, dict[str, int]]
    score: ReadinessScore
    ai_profile: AIProfile | None
    thesis_fit: ThesisFit | None
    valuation: ValuationResult | None
    run: RunRecord | None = None


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
    ai_excerpts: dict[str, str] = {}
    texts: dict[str, str] = {}
    reviewed: list[str] = []
    empty: list[str] = []
    degraded: list[str] = []

    for doc_path in paths:
        relative_name = str(doc_path.relative_to(path))
        notify(f"Analysing {relative_name}")
        document = load_document(doc_path)
        if document.is_empty:
            empty.append(relative_name)
            continue
        # one stubborn document must never abort the whole review; failed stages
        # are recorded and surfaced in the report instead
        try:
            doc_findings, summary = analyze_document(document, provider, config, relative_name)
            findings.extend(doc_findings)
            if summary is not None:
                summaries[relative_name] = summary
        except Exception:
            degraded.append(f"{relative_name} (findings extraction failed)")
        if has_financial_content(document):
            notify(f"Extracting metrics from {relative_name}")
            try:
                metrics.extend(extract_metrics(document, provider, config, relative_name))
            except Exception:
                degraded.append(f"{relative_name} (metrics extraction failed)")
        excerpt = ai_excerpt(document)
        if excerpt is not None:
            ai_excerpts[relative_name] = excerpt
        texts[relative_name] = document.text
        reviewed.append(relative_name)

    notify("Cross-referencing documents (deep check)")
    findings.extend(cross_document_findings(summaries, deep_provider, config))

    metrics = dedupe_metrics(metrics)
    findings.extend(metric_conflicts(metrics))
    findings = aggregate_findings(findings)

    ai_profile = None
    if summaries:
        notify("Assessing AI adoption")
        ai_profile = assess_ai_adoption(summaries, findings, provider, excerpts=ai_excerpts)
        claim_flags = ai_claim_findings(ai_profile)
        if claim_flags:
            findings = aggregate_findings(findings + claim_flags)

    notify("Verifying evidence quotes")
    quotes_verified, quotes_checked = verify_findings(findings, texts)
    verify_metrics(metrics, texts)

    notify("Scoring the deal")
    score = score_deal(findings, provider)
    matrix = risk_matrix(findings)

    thesis_fit = None
    if thesis_path is not None:
        notify("Assessing thesis fit")
        thesis_fit = assess_thesis_fit(
            thesis_path.read_text(encoding="utf-8"),
            metrics,
            findings,
            provider,
            summaries=summaries,
        )

    valuation = None
    if metrics:
        notify("Building indicative valuation")
        context_facts = [fact for s in summaries.values() for fact in s.key_facts[:2]]
        context = "; ".join(context_facts[:8]) or "unknown"
        top_flags = [f"{f.title} ({f.severity})" for f in findings[:6]]
        valuation = indicative_valuation(
            metrics, context, top_flags, provider, ai_profile=ai_profile
        )

    run = RunRecord(
        vespera_version=vespera.__version__,
        model=config.model,
        ollama_host=config.ollama_host,
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        chunk_chars=config.chunk_chars,
        thesis_provided=thesis_path is not None,
        evidence_quotes_verified=quotes_verified,
        evidence_quotes_checked=quotes_checked,
    )

    return DealAnalysis(
        documents=reviewed,
        empty_documents=empty,
        degraded_documents=degraded,
        metrics=metrics,
        findings=findings,
        risk_matrix=matrix,
        score=score,
        ai_profile=ai_profile,
        thesis_fit=thesis_fit,
        valuation=valuation,
        run=run,
    )
