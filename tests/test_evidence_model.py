"""Tests for evidence_model.py — Pydantic schemas."""
import pytest
from agents.copilot.evidence_model import (
    Source, SourceType, ValidationStatus, Claim, ClaimType,
    Calculation, CopilotResponse, CopilotState
)


class TestSource:
    def test_source_creation(self):
        s = Source(
            id="src-1",
            source_type=SourceType.NEWS_ARTICLE,
            title="AAPL Revenue Beats Estimates",
            publisher="Reuters",
            url="https://reuters.com/aapl",
            retrieved_at="2026-01-01T00:00:00+00:00",
            excerpt="Apple reported Q4 revenue of $124B, beating estimates.",
        )
        assert s.id == "src-1"
        assert s.source_type == SourceType.NEWS_ARTICLE
        assert s.validation_status == ValidationStatus.RETRIEVED

    def test_source_truncates_excerpt_at_600(self):
        long_text = "x" * 700
        with pytest.raises(Exception):
            Source(
                id="src-1",
                source_type=SourceType.MARKET_DATA,
                title="Test",
                retrieved_at="2026-01-01T00:00:00+00:00",
                excerpt=long_text,  # exceeds 600 char limit
            )

    def test_source_optional_fields(self):
        s = Source(
            id="src-2",
            source_type=SourceType.FINANCIAL_STATEMENT,
            title="Income Statement",
            retrieved_at="2026-01-01T00:00:00+00:00",
            excerpt="Revenue: $10B",
        )
        assert s.url is None
        assert s.publisher is None
        assert s.published_at is None

    def test_now_iso_returns_iso_string(self):
        result = Source.now_iso()
        assert "T" in result and "+" in result or "Z" in result


class TestClaim:
    def test_claim_defaults(self):
        c = Claim(text="Revenue grew 12%.")
        assert c.claim_type == ClaimType.UNKNOWN
        assert c.source_ids == []
        assert c.verified is False

    def test_claim_with_sources(self):
        c = Claim(
            text="Revenue grew 12% YoY.",
            claim_type=ClaimType.FACT,
            source_ids=["src-1", "src-3"],
            verified=True,
        )
        assert len(c.source_ids) == 2


class TestCalculation:
    def test_available_calculation(self):
        calc = Calculation(
            label="Revenue Growth YoY",
            value="+12.4%",
            raw_value=12.4,
            method="(Revenue 2024 / Revenue 2023) − 1",
            period="2023→2024",
            available=True,
        )
        assert calc.available is True
        assert calc.raw_value == 12.4

    def test_unavailable_calculation(self):
        calc = Calculation(
            label="Revenue Growth YoY",
            value="N/A",
            method="",
            available=False,
            unavailable_reason="Fewer than 2 periods available",
        )
        assert calc.available is False
        assert "periods" in calc.unavailable_reason


class TestCopilotState:
    def test_initial_state(self):
        state = CopilotState(
            session_id="sess-1",
            question="What is AAPL's revenue trend?",
            ticker="AAPL",
            market="US",
        )
        assert state.sources == []
        assert state.calculations == []
        assert state.aborted is False
        assert state.citation_validation_passed is True

    def test_state_model_dump_roundtrip(self):
        state = CopilotState(
            session_id="sess-2",
            question="How is margin trending?",
            ticker="MSFT",
            market="US",
        )
        dumped = state.model_dump()
        rehydrated = CopilotState(**dumped)
        assert rehydrated.ticker == "MSFT"
