"""Tests for calculator.py — deterministic financial calculations."""
import pytest
from agents.copilot.calculator import (
    revenue_growth_yoy,
    gross_margin_change,
    net_margin_change,
    price_from_52w_high,
    price_from_52w_low,
    revenue_cagr,
    run_calculations,
)
from agents.copilot.evidence_model import CopilotState


# ── fixtures ──────────────────────────────────────────────────────────────────

INCOME_2_PERIODS = [
    # newest first
    {"year": "2024", "revenue": 120_000_000_000, "gross_margin": 0.45, "net_margin": 0.25, "op_margin": 0.30},
    {"year": "2023", "revenue": 100_000_000_000, "gross_margin": 0.42, "net_margin": 0.22, "op_margin": 0.27},
]

INCOME_3_PERIODS = [
    {"year": "2024", "revenue": 120e9, "gross_margin": 0.45, "net_margin": 0.25, "op_margin": 0.30},
    {"year": "2023", "revenue": 100e9, "gross_margin": 0.42, "net_margin": 0.22, "op_margin": 0.27},
    {"year": "2022", "revenue":  80e9, "gross_margin": 0.40, "net_margin": 0.20, "op_margin": 0.25},
]

FACTS_WITH_PRICE = {
    "price": 175.0,
    "year_high": 200.0,
    "year_low": 130.0,
    "income": INCOME_2_PERIODS,
}


# ── revenue_growth_yoy ────────────────────────────────────────────────────────

class TestRevenueGrowthYoY:
    def test_normal_growth(self):
        calc = revenue_growth_yoy(INCOME_2_PERIODS, [], "AAPL")
        assert calc.available is True
        assert calc.raw_value == pytest.approx(20.0, abs=0.01)
        assert "+" in calc.value

    def test_negative_growth(self):
        income = [
            {"year": "2024", "revenue": 80e9, "gross_margin": 0.40, "net_margin": 0.20},
            {"year": "2023", "revenue": 100e9, "gross_margin": 0.42, "net_margin": 0.22},
        ]
        calc = revenue_growth_yoy(income, [], "TEST")
        assert calc.available is True
        assert calc.raw_value == pytest.approx(-20.0, abs=0.01)
        assert "-" in calc.value

    def test_zero_prior_revenue(self):
        income = [
            {"year": "2024", "revenue": 100e9},
            {"year": "2023", "revenue": 0},
        ]
        calc = revenue_growth_yoy(income, [], "TEST")
        assert calc.available is False
        assert "zero" in calc.unavailable_reason.lower()

    def test_single_period(self):
        calc = revenue_growth_yoy(INCOME_2_PERIODS[:1], [], "TEST")
        assert calc.available is False

    def test_empty_income(self):
        calc = revenue_growth_yoy([], [], "TEST")
        assert calc.available is False

    def test_missing_revenue_field(self):
        income = [{"year": "2024"}, {"year": "2023"}]
        calc = revenue_growth_yoy(income, [], "TEST")
        assert calc.available is False


# ── gross_margin_change ───────────────────────────────────────────────────────

class TestGrossMarginChange:
    def test_margin_expansion(self):
        calc = gross_margin_change(INCOME_2_PERIODS, [], "AAPL")
        assert calc.available is True
        # 0.45 - 0.42 = 0.03 → 3.0 pp
        assert calc.raw_value == pytest.approx(3.0, abs=0.01)
        assert "pp" in calc.value

    def test_margin_contraction(self):
        income = [
            {"year": "2024", "gross_margin": 0.40},
            {"year": "2023", "gross_margin": 0.45},
        ]
        calc = gross_margin_change(income, [], "TEST")
        assert calc.available is True
        assert calc.raw_value == pytest.approx(-5.0, abs=0.01)

    def test_missing_margin(self):
        income = [{"year": "2024"}, {"year": "2023"}]
        calc = gross_margin_change(income, [], "TEST")
        assert calc.available is False


# ── net_margin_change ─────────────────────────────────────────────────────────

class TestNetMarginChange:
    def test_net_margin_expansion(self):
        calc = net_margin_change(INCOME_2_PERIODS, [], "AAPL")
        # 0.25 - 0.22 = 0.03 → 3.0 pp
        assert calc.available is True
        assert calc.raw_value == pytest.approx(3.0, abs=0.01)

    def test_missing_net_margin(self):
        income = [{"year": "2024"}, {"year": "2023"}]
        calc = net_margin_change(income, [], "TEST")
        assert calc.available is False


# ── price_from_52w_high / low ─────────────────────────────────────────────────

class TestPriceReturns:
    def test_discount_from_high(self):
        calc = price_from_52w_high(FACTS_WITH_PRICE)
        assert calc.available is True
        # 175/200 - 1 = -12.5%
        assert calc.raw_value == pytest.approx(-12.5, abs=0.01)

    def test_premium_over_low(self):
        calc = price_from_52w_low(FACTS_WITH_PRICE)
        assert calc.available is True
        # 175/130 - 1 = 34.6%
        assert calc.raw_value == pytest.approx(34.615, abs=0.01)

    def test_missing_price(self):
        calc = price_from_52w_high({"year_high": 200.0})
        assert calc.available is False

    def test_zero_high(self):
        calc = price_from_52w_high({"price": 100.0, "year_high": 0.0})
        assert calc.available is False


# ── revenue_cagr ──────────────────────────────────────────────────────────────

class TestRevenueCagr:
    def test_3_period_cagr(self):
        calc = revenue_cagr(INCOME_3_PERIODS, [], "AAPL")
        assert calc.available is True
        # (120/80)^(1/2) - 1 = 22.47%
        assert calc.raw_value == pytest.approx(22.47, abs=0.1)

    def test_single_period(self):
        calc = revenue_cagr(INCOME_3_PERIODS[:1], [], "TEST")
        assert calc.available is False

    def test_negative_base(self):
        income = [
            {"year": "2024", "revenue": 100e9},
            {"year": "2023", "revenue": -10e9},
        ]
        calc = revenue_cagr(income, [], "TEST")
        assert calc.available is False


# ── run_calculations (integration) ───────────────────────────────────────────

class TestRunCalculations:
    def test_populates_calculations_on_state(self):
        state = CopilotState(
            session_id="s1",
            question="How is revenue trending?",
            ticker="AAPL",
            market="US",
            financial_facts=FACTS_WITH_PRICE | {"income": INCOME_2_PERIODS},
            sources=[],
        )
        updated = run_calculations(state)
        assert len(updated.calculations) > 0

    def test_empty_facts_returns_unavailable_calcs(self):
        state = CopilotState(
            session_id="s1",
            question="Test",
            ticker="AAPL",
            market="US",
            financial_facts={},
            sources=[],
        )
        updated = run_calculations(state)
        # All calcs should be unavailable
        assert all(not c.available for c in updated.calculations)
