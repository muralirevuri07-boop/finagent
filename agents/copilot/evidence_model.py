"""
evidence_model.py — Pydantic schemas for the AI Research Copilot.

Every source retrieved in a copilot session is represented as a Source object
with a stable ID that the LLM cites by reference.  Citation validation checks
that every ID the LLM returns actually exists in the evidence set for that
request — fabricated references are caught and flagged before the answer
reaches the frontend.
"""

from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


# ── Source type taxonomy ──────────────────────────────────────────────────────

class SourceType(str, Enum):
    NEWS_ARTICLE        = "news_article"
    SEARCH_RESULT       = "search_result"
    MARKET_DATA         = "market_data"
    FINANCIAL_STATEMENT = "financial_statement"
    CALCULATION         = "calculation"
    PROFILE_DATA        = "profile_data"


class ValidationStatus(str, Enum):
    RETRIEVED  = "retrieved"    # Returned by provider, not further verified
    CALCULATED = "calculated"   # Deterministic computation from validated inputs
    UNVERIFIED = "unverified"   # Could not confirm against original document


# ── Core evidence unit ────────────────────────────────────────────────────────

class Source(BaseModel):
    """A single retrievable evidence item with full provenance."""
    id: str = Field(..., description="Stable ID within session, e.g. 'src-1'")
    source_type: SourceType
    title: str
    publisher: Optional[str] = None
    url: Optional[str] = None           # Never fabricated; None when unavailable
    published_at: Optional[str] = None  # ISO8601 when available from provider
    retrieved_at: str                   # Always set at retrieval time
    excerpt: str = Field(..., max_length=600)
    ticker: Optional[str] = None
    reporting_period: Optional[str] = None  # e.g. "FY2024", "Q3 2024"
    validation_status: ValidationStatus = ValidationStatus.RETRIEVED

    @classmethod
    def now_iso(cls) -> str:
        return datetime.now(timezone.utc).isoformat()


# ── Claim with citation references ───────────────────────────────────────────

class ClaimType(str, Enum):
    FACT        = "fact"          # Directly sourced from retrieved evidence
    CALCULATION = "calculation"   # Derived from deterministic computation
    INTERPRETATION = "interpretation"  # LLM reasoning over evidence
    UNKNOWN     = "unknown"


class Claim(BaseModel):
    """A single factual or interpretive claim made in the answer."""
    text: str
    claim_type: ClaimType = ClaimType.UNKNOWN
    source_ids: List[str] = Field(default_factory=list)
    verified: bool = False
    limitation: Optional[str] = None   # Why verification is incomplete


# ── Deterministic calculation result ─────────────────────────────────────────

class Calculation(BaseModel):
    label: str               # e.g. "Revenue Growth YoY"
    value: str               # Formatted result, e.g. "+12.4%"
    raw_value: Optional[float] = None
    method: str              # Description of the formula
    period: Optional[str] = None
    currency: Optional[str] = None
    source_id: Optional[str] = None   # Points to the financial_statement source
    available: bool = True
    unavailable_reason: Optional[str] = None


# ── Full copilot response ─────────────────────────────────────────────────────

class CopilotResponse(BaseModel):
    session_id: str
    question: str
    ticker: str
    market: str
    answer: str                        # Direct, grounded answer
    key_findings: List[str] = Field(default_factory=list)
    claims: List[Claim] = Field(default_factory=list)
    sources: List[Source] = Field(default_factory=list)
    calculations: List[Calculation] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    unresolved: List[str] = Field(default_factory=list)
    conflicting_evidence: List[str] = Field(default_factory=list)
    data_warnings: List[str] = Field(default_factory=list)
    citation_validation_passed: bool = True
    citation_issues: List[str] = Field(default_factory=list)
    latency_ms: Optional[int] = None


# ── Copilot LangGraph state ───────────────────────────────────────────────────

class CopilotState(BaseModel):
    """State object passed through the copilot LangGraph pipeline."""
    # Inputs
    session_id: str
    question: str
    ticker: str
    market: str
    # Accumulated through pipeline
    sources: List[Source] = Field(default_factory=list)
    calculations: List[Calculation] = Field(default_factory=list)
    financial_facts: dict = Field(default_factory=dict)
    historical_facts: dict = Field(default_factory=dict)
    # LLM output (pre-validation)
    raw_answer: str = ""
    raw_claims: List[dict] = Field(default_factory=list)
    raw_key_findings: List[str] = Field(default_factory=list)
    raw_limitations: List[str] = Field(default_factory=list)
    raw_unresolved: List[str] = Field(default_factory=list)
    raw_conflicting: List[str] = Field(default_factory=list)
    raw_data_warnings: List[str] = Field(default_factory=list)
    # Validation
    citation_validation_passed: bool = True
    citation_issues: List[str] = Field(default_factory=list)
    # Error handling
    error: Optional[str] = None
    aborted: bool = False
    abort_reason: Optional[str] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)
