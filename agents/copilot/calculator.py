"""
calculator.py — Deterministic financial calculations for the copilot.

No LLM involved.  Every calculation is formula-derived from raw FMP data.
Results are attached to the state as Calculation objects, each with a
source_id pointing to the financial_statement Source that supplied the data.

Edge cases handled:
  - Division by zero / sign-flip (negative base)
  - Missing data  → Calculation(available=False)
  - Single-period data  → YoY calcs not possible
"""

from __future__ import annotations
from typing import List, Optional, Dict, Any

from agents.copilot.evidence_model import Calculation, CopilotState, Source, SourceType


# ── helpers ───────────────────────────────────────────────────────────────────

def _pct(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f}%"


def _unavailable(label: str, reason: str) -> Calculation:
    return Calculation(
        label=label,
        value="N/A",
        method="",
        available=False,
        unavailable_reason=reason,
    )


def _find_fin_source_id(sources: List[Source], ticker: str, year: str) -> Optional[str]:
    """Return the Source id of the income statement for a given year."""
    for s in sources:
        if (
            s.source_type == SourceType.FINANCIAL_STATEMENT
            and "Income Statement" in s.title
            and year in s.title
        ):
            return s.id
    return None


# ── individual calculators ────────────────────────────────────────────────────

def revenue_growth_yoy(income: List[Dict], sources: List[Source], ticker: str) -> Calculation:
    """Year-over-year revenue growth: (rev_latest / rev_prior - 1) × 100."""
    label = "Revenue Growth YoY"
    if not income or len(income) < 2:
        return _unavailable(label, "Fewer than 2 annual periods available")

    current = income[0]  # newest
    prior   = income[1]
    rev_cur = current.get("revenue")
    rev_pri = prior.get("revenue")

    if rev_cur is None or rev_pri is None:
        return _unavailable(label, "Revenue data missing")
    if rev_pri == 0:
        return _unavailable(label, "Prior-year revenue is zero — growth undefined")

    growth = (rev_cur / rev_pri - 1) * 100
    year_c = current.get("year", "")
    year_p = prior.get("year", "")
    src_id = _find_fin_source_id(sources, ticker, year_c)

    return Calculation(
        label=label,
        value=_pct(growth),
        raw_value=round(growth, 4),
        method=f"(Revenue {year_c} / Revenue {year_p}) − 1",
        period=f"{year_p}→{year_c}",
        source_id=src_id,
        available=True,
    )


def gross_margin_change(income: List[Dict], sources: List[Source], ticker: str) -> Calculation:
    """Change in gross margin between latest and prior year (pp = percentage points)."""
    label = "Gross Margin Change (pp)"
    if not income or len(income) < 2:
        return _unavailable(label, "Fewer than 2 annual periods available")

    cur_gm = income[0].get("gross_margin")
    pri_gm = income[1].get("gross_margin")

    if cur_gm is None or pri_gm is None:
        return _unavailable(label, "Gross margin ratio missing from financial data")

    delta_pp = (cur_gm - pri_gm) * 100
    year_c = income[0].get("year", "")
    year_p = income[1].get("year", "")
    src_id = _find_fin_source_id(sources, ticker, year_c)

    return Calculation(
        label=label,
        value=f"{delta_pp:+.1f} pp",
        raw_value=round(delta_pp, 4),
        method=f"Gross margin {year_c} − Gross margin {year_p} (in percentage points)",
        period=f"{year_p}→{year_c}",
        source_id=src_id,
        available=True,
    )


def net_margin_change(income: List[Dict], sources: List[Source], ticker: str) -> Calculation:
    """Change in net profit margin between latest and prior year (pp)."""
    label = "Net Margin Change (pp)"
    if not income or len(income) < 2:
        return _unavailable(label, "Fewer than 2 annual periods available")

    cur_nm = income[0].get("net_margin")
    pri_nm = income[1].get("net_margin")

    if cur_nm is None or pri_nm is None:
        return _unavailable(label, "Net margin ratio missing from financial data")

    delta_pp = (cur_nm - pri_nm) * 100
    year_c = income[0].get("year", "")
    year_p = income[1].get("year", "")
    src_id = _find_fin_source_id(sources, ticker, year_c)

    return Calculation(
        label=label,
        value=f"{delta_pp:+.1f} pp",
        raw_value=round(delta_pp, 4),
        method=f"Net margin {year_c} − Net margin {year_p} (in percentage points)",
        period=f"{year_p}→{year_c}",
        source_id=src_id,
        available=True,
    )


def price_from_52w_high(facts: Dict[str, Any]) -> Calculation:
    """How far the current price is from its 52-week high."""
    label = "Discount from 52W High"
    price = facts.get("price")
    high  = facts.get("year_high")

    if price is None or high is None:
        return _unavailable(label, "Current price or 52-week high unavailable")
    if high == 0:
        return _unavailable(label, "52-week high is zero")

    drawdown = (price / high - 1) * 100

    return Calculation(
        label=label,
        value=_pct(drawdown),
        raw_value=round(drawdown, 4),
        method="(Current price / 52W high) − 1",
        available=True,
    )


def price_from_52w_low(facts: Dict[str, Any]) -> Calculation:
    """How far the current price is above its 52-week low."""
    label = "Premium over 52W Low"
    price = facts.get("price")
    low   = facts.get("year_low")

    if price is None or low is None:
        return _unavailable(label, "Current price or 52-week low unavailable")
    if low == 0:
        return _unavailable(label, "52-week low is zero")

    premium = (price / low - 1) * 100

    return Calculation(
        label=label,
        value=_pct(premium),
        raw_value=round(premium, 4),
        method="(Current price / 52W low) − 1",
        available=True,
    )


def revenue_cagr(income: List[Dict], sources: List[Source], ticker: str) -> Calculation:
    """Compound annual growth rate of revenue across all available periods."""
    label = "Revenue CAGR"
    if not income or len(income) < 2:
        return _unavailable(label, "Fewer than 2 annual periods available")

    rev_latest = income[0].get("revenue")
    rev_first  = income[-1].get("revenue")
    n_years    = len(income) - 1

    if rev_latest is None or rev_first is None:
        return _unavailable(label, "Revenue data missing for CAGR calculation")
    if rev_first <= 0:
        return _unavailable(label, "Base-year revenue is zero or negative — CAGR undefined")

    cagr = ((rev_latest / rev_first) ** (1 / n_years) - 1) * 100
    year_latest = income[0].get("year", "")
    year_first  = income[-1].get("year", "")
    src_id = _find_fin_source_id(sources, ticker, year_latest)

    return Calculation(
        label=label,
        value=_pct(cagr),
        raw_value=round(cagr, 4),
        method=f"(Revenue {year_latest} / Revenue {year_first})^(1/{n_years}) − 1",
        period=f"{year_first}–{year_latest}",
        source_id=src_id,
        available=True,
    )


# ── main node ─────────────────────────────────────────────────────────────────

def run_calculations(state: CopilotState) -> CopilotState:
    """LangGraph node: run all deterministic calculations."""
    facts   = state.financial_facts or {}
    income  = facts.get("income", [])
    sources = state.sources or []
    ticker  = (state.ticker or "").upper()

    calcs: List[Calculation] = [
        revenue_growth_yoy(income, sources, ticker),
        gross_margin_change(income, sources, ticker),
        net_margin_change(income, sources, ticker),
        price_from_52w_high(facts),
        price_from_52w_low(facts),
        revenue_cagr(income, sources, ticker),
    ]

    # Only keep available ones in the response — unavailable still go in
    # so the synthesiser knows which calcs couldn't be done
    return CopilotState(**{**state.model_dump(), "calculations": calcs})
