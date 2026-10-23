"""
historical_financials_agent.py
Fetches 10-year annual financial statements from Financial Modeling Prep (FMP).

Endpoints used (free tier, 250 req/day):
  /income-statement/{symbol}?period=annual&limit=10
  /balance-sheet-statement/{symbol}?period=annual&limit=10
  /cash-flow-statement/{symbol}?period=annual&limit=10

Non-equity markets (Crypto/Forex/Commodity) are skipped — returns empty dict.
"""

from __future__ import annotations
import os
import urllib.request
import urllib.parse
import json
from typing import Optional

FMP_BASE = "https://financialmodelingprep.com/stable"

NON_EQUITY_MARKETS = {"Crypto", "Forex", "Commodity"}

# ── helpers ──────────────────────────────────────────────────────────────────

def _get(path: str, api_key: str) -> list[dict]:
    sep = "&" if "?" in path else "?"
    url = f"{FMP_BASE}{path}{sep}apikey={api_key}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "FinAgent/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _fmt_large(v) -> str:
    """Format large numbers as B / M with 2dp."""
    try:
        n = float(v)
    except (TypeError, ValueError):
        return "N/A"
    if abs(n) >= 1e9:
        return f"{n/1e9:.2f}B"
    if abs(n) >= 1e6:
        return f"{n/1e6:.2f}M"
    return f"{n:,.0f}"


def _pct(v) -> str:
    try:
        return f"{float(v)*100:.1f}%"
    except (TypeError, ValueError):
        return "N/A"


def _safe(v) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ── FMP symbol mapping ────────────────────────────────────────────────────────

def _fmp_symbol(ticker: str, market: str) -> str:
    """
    FMP uses plain tickers for US; for non-US append exchange suffix.
    yfinance suffixes: .L (LSE), .DE (Frankfurt/XETRA), .T (Tokyo),
                       .HK (HK), .SI (Singapore), .NS / .BO (NSE/BSE)
    FMP uses: .L, .DE, .T, .HK, .SI, .NS, .BO  (same convention)
    """
    # Already has a suffix — pass through
    if "." in ticker:
        return ticker.upper()

    SUFFIX_MAP = {
        "LSE":       ".L",
        "Frankfurt": ".DE",
        "Tokyo":     ".T",
        "HongKong":  ".HK",
        "Singapore": ".SI",
        "NSE":       ".NS",
        "BSE":       ".BO",
    }
    suffix = SUFFIX_MAP.get(market, "")
    return f"{ticker.upper()}{suffix}"


# ── main agent function ───────────────────────────────────────────────────────

def historical_financials_agent(state: dict) -> dict:
    ticker  = state.get("ticker", "")
    market  = state.get("market", "US")
    api_key = os.getenv("FMP_API_KEY", "")

    if market in NON_EQUITY_MARKETS or not api_key or not ticker:
        return {**state, "historical_financials": {}}

    sym = _fmp_symbol(ticker, market)

    # Fetch all three statements in parallel-ish (sequential, free tier)
    income_raw    = _get(f"/income-statement/{sym}?period=annual&limit=10",       api_key)
    balance_raw   = _get(f"/balance-sheet-statement/{sym}?period=annual&limit=10", api_key)
    cashflow_raw  = _get(f"/cash-flow-statement/{sym}?period=annual&limit=10",     api_key)

    if not income_raw and not balance_raw and not cashflow_raw:
        return {**state, "historical_financials": {"available": False, "reason": "No FMP data for this symbol"}}

    # ── Income Statement ──────────────────────────────────────────────────────
    income_table = []
    for row in income_raw:
        income_table.append({
            "year":             row.get("calendarYear") or row.get("date", "")[:4],
            "revenue":          _fmt_large(row.get("revenue")),
            "gross_profit":     _fmt_large(row.get("grossProfit")),
            "operating_income": _fmt_large(row.get("operatingIncome")),
            "net_income":       _fmt_large(row.get("netIncome")),
            "ebitda":           _fmt_large(row.get("ebitda")),
            "eps":              round(float(row.get("eps", 0) or 0), 2),
            "gross_margin":     _pct(row.get("grossProfitRatio")),
            "op_margin":        _pct(row.get("operatingIncomeRatio")),
            "net_margin":       _pct(row.get("netIncomeRatio")),
            # raw for trend calcs
            "_revenue_raw":     _safe(row.get("revenue")),
            "_net_income_raw":  _safe(row.get("netIncome")),
        })

    # ── Balance Sheet ─────────────────────────────────────────────────────────
    balance_table = []
    for row in balance_raw:
        balance_table.append({
            "year":               row.get("calendarYear") or row.get("date", "")[:4],
            "total_assets":       _fmt_large(row.get("totalAssets")),
            "total_liabilities":  _fmt_large(row.get("totalLiabilities")),
            "total_equity":       _fmt_large(row.get("totalStockholdersEquity")),
            "cash":               _fmt_large(row.get("cashAndCashEquivalents")),
            "total_debt":         _fmt_large(row.get("totalDebt")),
            "net_debt":           _fmt_large(row.get("netDebt")),
            "book_value_share":   round(float(row.get("bookValuePerShare", 0) or 0), 2),
            "_equity_raw":        _safe(row.get("totalStockholdersEquity")),
            "_debt_raw":          _safe(row.get("totalDebt")),
        })

    # ── Cash Flow ─────────────────────────────────────────────────────────────
    cashflow_table = []
    for row in cashflow_raw:
        cashflow_table.append({
            "year":                  row.get("calendarYear") or row.get("date", "")[:4],
            "operating_cf":          _fmt_large(row.get("operatingCashFlow")),
            "capex":                 _fmt_large(row.get("capitalExpenditure")),
            "free_cashflow":         _fmt_large(row.get("freeCashFlow")),
            "dividends_paid":        _fmt_large(row.get("dividendsPaid")),
            "share_buybacks":        _fmt_large(row.get("commonStockRepurchased")),
            "_fcf_raw":              _safe(row.get("freeCashFlow")),
            "_operating_cf_raw":     _safe(row.get("operatingCashFlow")),
        })

    # ── Trend summary ─────────────────────────────────────────────────────────
    trends = {}
    if len(income_table) >= 2:
        rev_first = income_table[-1].get("_revenue_raw")
        rev_last  = income_table[0].get("_revenue_raw")
        if rev_first and rev_last and rev_first > 0:
            yrs  = len(income_table) - 1
            cagr = ((rev_last / rev_first) ** (1 / yrs) - 1) * 100
            trends["revenue_cagr"] = f"{cagr:+.1f}%"

        ni_first = income_table[-1].get("_net_income_raw")
        ni_last  = income_table[0].get("_net_income_raw")
        if ni_first and ni_last:
            trends["net_income_trend"] = "↑ Expanding" if ni_last > ni_first else "↓ Contracting"

    if len(balance_table) >= 2:
        debt_first = balance_table[-1].get("_debt_raw")
        debt_last  = balance_table[0].get("_debt_raw")
        if debt_first is not None and debt_last is not None:
            trends["debt_trend"] = "↑ Rising" if debt_last > debt_first else "↓ Falling"

    if len(cashflow_table) >= 2:
        fcf_first = cashflow_table[-1].get("_fcf_raw")
        fcf_last  = cashflow_table[0].get("_fcf_raw")
        if fcf_first is not None and fcf_last is not None:
            trends["fcf_trend"] = "↑ Improving" if fcf_last > fcf_first else "↓ Deteriorating"

    result = {
        "available":      True,
        "symbol":         sym,
        "years_available": len(income_table),
        "income_statement": income_table,
        "balance_sheet":    balance_table,
        "cash_flow":        cashflow_table,
        "trends":           trends,
    }

    return {**state, "historical_financials": result}
