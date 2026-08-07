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
