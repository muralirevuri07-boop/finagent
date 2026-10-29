"""
historical_financials_agent.py
Fetches 10-year annual financial statements.

Primary: Financial Modeling Prep (FMP) — covers US + EU well on free tier.
Fallback: Alpha Vantage INCOME_STATEMENT / BALANCE_SHEET / CASH_FLOW —
          covers NSE/BSE and other international markets FMP free tier misses.

Non-equity markets (Crypto/Forex/Commodity) are skipped — returns empty dict.
"""

from __future__ import annotations
import os
import urllib.request
import urllib.parse
import json
import requests
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
        "source":         "FMP",
        "years_available": len(income_table),
        "income_statement": income_table,
        "balance_sheet":    balance_table,
        "cash_flow":        cashflow_table,
        "trends":           trends,
    }

    return {**state, "historical_financials": result}


# ── Alpha Vantage fallback for non-US markets ─────────────────────────────────

def _av_get(function: str, symbol: str, api_key: str) -> list[dict]:
    """Fetch annual reports from Alpha Vantage with caching."""
    from agents.av_cache import get as av_get, set as av_set
    cached = av_get(symbol, function)
    if cached is not None:
        return cached
    url = (
        f"https://www.alphavantage.co/query"
        f"?function={function}&symbol={symbol}&apikey={api_key}"
    )
    try:
        r = requests.get(url, timeout=15)
        d = r.json()
        rows = d.get("annualReports", [])
        if rows:
            av_set(symbol, function, rows)
        return rows
    except Exception:
        return []


def _historical_financials_alpha_vantage(ticker: str, market: str) -> dict:
    """
    Fetch 10-year financials from Alpha Vantage for non-US / non-FMP markets.
    AV symbol format: plain ticker for US, NSE:TICKER for NSE, BSE:TICKER for BSE, etc.
    """
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "")
    if not api_key:
        return {"available": False, "reason": "No Alpha Vantage API key"}

    # Build AV symbol
    AV_PREFIX = {
        "NSE": "NSE:", "BSE": "BSE:", "LSE": "",
        "Tokyo": "", "HongKong": "", "Singapore": "",
    }
    base = ticker.split(".")[0] if "." in ticker else ticker
    prefix = AV_PREFIX.get(market, "")
    av_sym = f"{prefix}{base.upper()}"

    income_raw   = _av_get("INCOME_STATEMENT",  av_sym, api_key)
    balance_raw  = _av_get("BALANCE_SHEET",      av_sym, api_key)
    cashflow_raw = _av_get("CASH_FLOW",          av_sym, api_key)

    if not income_raw and not balance_raw and not cashflow_raw:
        return {"available": False, "reason": f"No Alpha Vantage data for {av_sym}"}

    def _s(row, *keys):
        for k in keys:
            v = row.get(k)
            if v and v not in ("None", "-"):
                try:
                    return float(v)
                except Exception:
                    pass
        return None

    income_table = []
    for row in income_raw[:10]:
        year = row.get("fiscalDateEnding", "")[:4]
        rev   = _s(row, "totalRevenue")
        gp    = _s(row, "grossProfit")
        oi    = _s(row, "operatingIncome", "ebit")
        ni    = _s(row, "netIncome")
        ebitda = _s(row, "ebitda")
        income_table.append({
            "year":             year,
            "revenue":          _fmt_large(rev),
            "gross_profit":     _fmt_large(gp),
            "operating_income": _fmt_large(oi),
            "net_income":       _fmt_large(ni),
            "ebitda":           _fmt_large(ebitda),
            "eps":              "N/A",
            "gross_margin":     f"{gp/rev*100:.1f}%" if rev and gp else "N/A",
            "op_margin":        f"{oi/rev*100:.1f}%" if rev and oi else "N/A",
            "net_margin":       f"{ni/rev*100:.1f}%" if rev and ni else "N/A",
            "_revenue_raw":     rev,
            "_net_income_raw":  ni,
        })

    balance_table = []
    for row in balance_raw[:10]:
        year  = row.get("fiscalDateEnding", "")[:4]
        ta    = _s(row, "totalAssets")
        tl    = _s(row, "totalLiabilities")
        eq    = _s(row, "totalShareholderEquity")
        cash  = _s(row, "cashAndCashEquivalentsAtCarryingValue", "cashAndShortTermInvestments")
        debt  = _s(row, "shortLongTermDebtTotal", "longTermDebtNoncurrent")
        balance_table.append({
            "year":              year,
            "total_assets":      _fmt_large(ta),
            "total_liabilities": _fmt_large(tl),
            "total_equity":      _fmt_large(eq),
            "cash":              _fmt_large(cash),
            "total_debt":        _fmt_large(debt),
            "net_debt":          _fmt_large((debt or 0) - (cash or 0)) if debt else "N/A",
            "book_value_share":  "N/A",
            "_equity_raw":       eq,
            "_debt_raw":         debt,
        })

    cashflow_table = []
    for row in cashflow_raw[:10]:
        year  = row.get("fiscalDateEnding", "")[:4]
        ocf   = _s(row, "operatingCashflow")
        capex = _s(row, "capitalExpenditures")
        fcf   = (ocf - abs(capex)) if ocf and capex else None
        div   = _s(row, "dividendPayout")
        cashflow_table.append({
            "year":            year,
            "operating_cf":    _fmt_large(ocf),
            "capex":           _fmt_large(capex),
            "free_cashflow":   _fmt_large(fcf),
            "dividends_paid":  _fmt_large(div),
            "share_buybacks":  "N/A",
            "_fcf_raw":        fcf,
            "_operating_cf_raw": ocf,
        })

    # Trends
    trends = {}
    if len(income_table) >= 2:
        r0 = income_table[-1].get("_revenue_raw")
        r1 = income_table[0].get("_revenue_raw")
        if r0 and r1 and r0 > 0:
            yrs = len(income_table) - 1
            cagr = ((r1/r0)**(1/yrs) - 1)*100
            trends["revenue_cagr"] = f"{cagr:+.1f}%"
        ni0 = income_table[-1].get("_net_income_raw")
        ni1 = income_table[0].get("_net_income_raw")
        if ni0 and ni1:
            trends["net_income_trend"] = "↑ Expanding" if ni1 > ni0 else "↓ Contracting"
    if len(balance_table) >= 2:
        d0 = balance_table[-1].get("_debt_raw")
        d1 = balance_table[0].get("_debt_raw")
        if d0 is not None and d1 is not None:
            trends["debt_trend"] = "↑ Rising" if d1 > d0 else "↓ Falling"
    if len(cashflow_table) >= 2:
        f0 = cashflow_table[-1].get("_fcf_raw")
        f1 = cashflow_table[0].get("_fcf_raw")
        if f0 is not None and f1 is not None:
            trends["fcf_trend"] = "↑ Improving" if f1 > f0 else "↓ Deteriorating"

    return {
        "available":        True,
        "symbol":           av_sym,
        "source":           "AlphaVantage",
        "years_available":  len(income_table),
        "income_statement": income_table,
        "balance_sheet":    balance_table,
        "cash_flow":        cashflow_table,
        "trends":           trends,
    }


def historical_financials_agent_global(state: dict) -> dict:
    """
    Wrapper that tries FMP first, then Alpha Vantage for non-US markets.
    Use this in the LangGraph pipeline instead of historical_financials_agent.
    """
    ticker = state.get("ticker", "")
    market = state.get("market", "US")

    if market in NON_EQUITY_MARKETS or not ticker:
        return {**state, "historical_financials": {}}

    # 1. Try FMP
    fmp_state = historical_financials_agent(state)
    fmp_result = fmp_state.get("historical_financials", {})
    if fmp_result.get("available") and fmp_result.get("years_available", 0) > 0:
        return fmp_state

    # 2. Fallback to Alpha Vantage
    av_result = _historical_financials_alpha_vantage(ticker, market)
    return {**state, "historical_financials": av_result}
