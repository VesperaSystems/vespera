"""Pydantic models for structured findings."""

from typing import Literal, get_args

from pydantic import BaseModel, Field, field_validator

Category = Literal[
    "parties",
    "important dates",
    "contract type",
    "governing law",
    "change-of-control clauses",
    "termination rights",
    "assignment restrictions",
    "exclusivity",
    "unusual obligations",
    "material liabilities",
    "IP ownership / assignment",
    "confidentiality obligations",
    "missing signatures",
    "missing documents explicitly referenced elsewhere",
    "inconsistencies between documents",
    "potential red flags",
]

CATEGORY_ORDER: list[str] = list(get_args(Category))

Severity = Literal["info", "low", "medium", "high"]

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2, "info": 3}


class Finding(BaseModel):
    category: str
    title: str
    summary: str
    severity: Severity
    source_file: str
    source_page: int | None
    evidence: str
    confidence: float = Field(ge=0.0, le=1.0)


class ExtractedFinding(BaseModel):
    """What the LLM returns for a chunk; source location is stamped by code."""

    category: Category
    title: str
    summary: str
    severity: Severity
    evidence: str = Field(description="Short verbatim excerpt from the text, max ~40 words")
    confidence: float = Field(ge=0.0, le=1.0, description="Between 0.0 and 1.0")

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_percentage(cls, value):
        # local models often answer 90 when they mean 0.9
        if isinstance(value, (int, float)) and 1.0 < value <= 100.0:
            return value / 100.0
        return value


class ChunkFindings(BaseModel):
    findings: list[ExtractedFinding] = Field(
        default_factory=list,
        description="Findings supported by the supplied text. Empty if none.",
    )


class DocumentSummary(BaseModel):
    """One-line facts per document, used for the cross-document pass."""

    contract_type: str = Field(description="e.g. 'Master Services Agreement', or 'unknown'")
    parties: list[str] = Field(default_factory=list)
    key_dates: list[str] = Field(default_factory=list)
    referenced_documents: list[str] = Field(
        default_factory=list,
        description="Other documents, schedules, or exhibits this document explicitly refers to",
    )
    key_facts: list[str] = Field(
        default_factory=list,
        description=(
            "Material factual assertions worth cross-checking: monetary amounts and "
            "commitments, ownership claims (e.g. who owns which IP), and key terms"
        ),
    )
    signed: bool = Field(description="Whether the document appears to be executed/signed")


class CrossDocumentFindings(BaseModel):
    findings: list[ExtractedFinding] = Field(default_factory=list)


MetricName = Literal[
    "revenue",
    "arr",
    "mrr",
    "revenue growth",
    "gross margin",
    "operating profit/loss",
    "ebitda",
    "net revenue retention",
    "cash balance",
    "runway",
    "customers",
    "churn",
]

MetricUnit = Literal["GBP", "USD", "EUR", "percent", "count", "months", "other"]


class ExtractedMetric(BaseModel):
    """What the LLM returns for one financial metric; source is stamped by code."""

    name: MetricName
    value_text: str = Field(description="The value exactly as written in the document")
    amount: float = Field(
        description=(
            "Numeric value: for currency metrics the amount in MILLIONS "
            "(e.g. £54,500,000 -> 54.5); for percent the percentage number; "
            "for counts/months the plain number"
        )
    )
    unit: MetricUnit
    period: str = Field(description="Period the value refers to, e.g. 'FY2025', or 'unknown'")
    evidence: str = Field(description="Short verbatim excerpt containing the value")


class ExtractedMetrics(BaseModel):
    metrics: list[ExtractedMetric] = Field(
        default_factory=list,
        description="Financial metrics explicitly stated in the text. Empty if none.",
    )


class KeyMetric(BaseModel):
    """A stamped, source-attributed metric."""

    name: str
    value_text: str
    amount: float
    unit: str
    period: str
    source_file: str
    source_page: int | None
    evidence: str


class ReadinessScore(BaseModel):
    score: int = Field(ge=0, le=100)
    label: str
    rationale: str


class ScoreRationale(BaseModel):
    rationale: str = Field(
        description="One sentence weighing the favourable signals against the flagged risks"
    )


class ThesisPoint(BaseModel):
    point: str
    evidence: str = Field(description="Which document/metric supports this, briefly")


class CriterionAssessment(BaseModel):
    criterion: str = Field(description="The thesis criterion being assessed, briefly")
    verdict: Literal["aligned", "conflict", "unknown"]
    evidence: str = Field(
        description="Which document or metric supports this verdict; 'none' for unknown"
    )


class ThesisAssessment(BaseModel):
    """One assessment per thesis criterion — the list may not be empty."""

    assessments: list[CriterionAssessment] = Field(min_length=1)


class ThesisFit(BaseModel):
    score: int = Field(ge=0, le=100, description="0 = clear mismatch, 100 = strong fit")
    aligned: list[ThesisPoint] = Field(default_factory=list)
    conflicts: list[ThesisPoint] = Field(default_factory=list)
    unknowns: list[str] = Field(
        default_factory=list,
        description="Thesis criteria the dataroom gives no evidence for either way",
    )


AIAspect = Literal["product", "operations", "engineering"]
AIVerdict = Literal["evidenced", "claimed-only", "absent", "unclear"]


class AIAspectAssessment(BaseModel):
    aspect: AIAspect
    verdict: AIVerdict = Field(
        description=(
            "'evidenced': documents show concrete AI/ML/LLM use (models, infrastructure, "
            "agentic workflows, named AI systems doing real work). 'claimed-only': AI is "
            "asserted in marketing or investor language but nothing technical supports it. "
            "'absent': documents cover this area and show no AI use. 'unclear': the "
            "documents don't cover this area."
        )
    )
    detail: str = Field(description="What the AI use or claim actually is, briefly")
    evidence: str = Field(description="Which document says so; 'none' for absent/unclear")


class AIAssessment(BaseModel):
    """One assessment per aspect (product, operations, engineering) — never empty."""

    aspects: list[AIAspectAssessment] = Field(min_length=1)
    automation_leverage: str = Field(
        description=(
            "One or two sentences: how much of this business's cost to serve looks "
            "addressable by AI/automation, based only on the evidence"
        )
    )


class AIProfile(BaseModel):
    """Code-derived AI adoption profile; the posture label is deterministic."""

    posture: str
    product_ai: str
    aspects: list[AIAspectAssessment]
    automation_leverage: str


class MultipleProposal(BaseModel):
    """LLM proposes multiples and assumptions; the arithmetic happens in code."""

    basis: Literal["revenue", "arr"]
    multiple_low: float = Field(gt=0)
    multiple_base: float = Field(gt=0)
    multiple_high: float = Field(gt=0)
    sector: str
    assumptions: list[str] = Field(description="Every assumption behind the chosen multiples")
    confidence: float = Field(ge=0.0, le=1.0)
    caveats: list[str] = Field(default_factory=list)

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_percentage(cls, value):
        if isinstance(value, (int, float)) and 1.0 < value <= 100.0:
            return value / 100.0
        return value


class ValuationResult(BaseModel):
    basis_metric: str
    basis_amount_millions: float
    currency: str
    multiple_low: float
    multiple_base: float
    multiple_high: float
    value_low_millions: float
    value_base_millions: float
    value_high_millions: float
    sector: str
    assumptions: list[str]
    confidence: float
    caveats: list[str]
