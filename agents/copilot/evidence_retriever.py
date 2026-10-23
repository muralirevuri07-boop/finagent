"""
evidence_retriever.py — Gathers structured evidence for the copilot.

Sources:
  1. Tavily search  — news / web, full metadata preserved (url, title, score, published_date)
  2. FMP quote      — real-time price data as a market_data Source
  3. FMP profile    — company overview as a profile_data Source
  4. FMP income / balance / cashflow — financial_statement Sources (latest 2 years)
  5. FMP historical EOD prices — market_data Source for price history

Security note: retrieved content is NEVER executed or interpolated into
code paths — it is stored as plain text excerpts.
"""

from __future__ import annotations
import os
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from agents.copilot.evidence_model import (
    Source, SourceType, ValidationStatus, CopilotState, Calculation
)

FMP_BASE = "https://financialmodelingprep.com/stable"
_SRC_COUNTER: int = 0  # Per-request counter reset via _reset_counter()


# ── helpers ───────────────────────────────────────────────────────────────────

def _reset_counter() -> None:
    global _SRC_COUNTER
    _SRC_COUNTER = 0


def _next_id() -> str:
    global _SRC_COUNTER
    _SRC_COUNTER += 1
    return f"src-{_SRC_COUNTER}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truncate(text: str, max_len: int = 500) -> str:
    if not text:
        return ""
    text = text.strip()
    return text[:max_len] + "…" if len(text) > max_len else text


def _fmp_get(path: str, api_key: str) -> Any:
    sep = "&" if "?" in path else "?"
    url = f"{FMP_BASE}{path}{sep}apikey={api_key}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "FinAgent/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _safe_float(v) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _fmt_large(v) -> str:
    try:
        n = float(v)
    except (TypeError, ValueError):
        return "N/A"
    if abs(n) >= 1e12:
        return f"${n/1e12:.2f}T"
    if abs(n) >= 1e9:
        return f"${n/1e9:.2f}B"
    if abs(n) >= 1e6:
        return f"${n/1e6:.2f}M"
    return f"${n:,.0f}"


# ── 1. Tavily news search ─────────────────────────────────────────────────────

def _retrieve_news(ticker: str, question: str, api_key: str, max_results: int = 6) -> List[Source]:
    """Call Tavily and preserve full metadata for every result."""
    if not api_key:
        return []

    query = f"{ticker} {question}"
    payload = json.dumps({
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",
        "include_answer": False,
        "include_raw_content": False,
    }).encode()

    try:
        req = urllib.request.Request(
            "https://api.tavily.com/search",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return []

    sources: List[Source] = []
    for item in data.get("results", []):
        content = item.get("content") or ""
        url     = item.get("url") or None
        title   = item.get("title") or (url or "Untitled article")
        # Determine publisher from domain
        publisher: Optional[str] = None
        if url:
            try:
                publisher = urllib.parse.urlparse(url).netloc.replace("www.", "")
            except Exception:
                pass

        sources.append(Source(
            id=_next_id(),
            source_type=SourceType.NEWS_ARTICLE,
            title=title[:200],
            publisher=publisher,
            url=url,
            published_at=item.get("published_date"),   # Tavily returns ISO string or None
            retrieved_at=_now(),
            excerpt=_truncate(content),
            ticker=ticker,
            validation_status=ValidationStatus.RETRIEVED,
        ))

    return sources


# ── 2. FMP market data ────────────────────────────────────────────────────────

def _retrieve_market_data(ticker: str, api_key: str) -> Optional[Source]:
    data = _fmp_get(f"/quote/{ticker}", api_key)
    if not data:
        return None
    quote = data[0] if isinstance(data, list) else data
    price   = _safe_float(quote.get("price"))
    chg_pct = _safe_float(quote.get("changesPercentage"))
    vol     = quote.get("volume")
    mcap    = quote.get("marketCap")
    hi52    = _safe_float(quote.get("yearHigh"))
    lo52    = _safe_float(quote.get("yearLow"))
    name    = quote.get("name") or ticker

    excerpt_parts = []
    if price is not None:
        excerpt_parts.append(f"Price: ${price:,.2f}")
    if chg_pct is not None:
        excerpt_parts.append(f"Change: {chg_pct:+.2f}%")
    if hi52 and lo52:
        excerpt_parts.append(f"52w range: ${lo52:,.2f}–${hi52:,.2f}")
    if vol:
        excerpt_parts.append(f"Volume: {vol:,}")
    if mcap:
        excerpt_parts.append(f"Market cap: {_fmt_large(mcap)}")

    return Source(
        id=_next_id(),
        source_type=SourceType.MARKET_DATA,
        title=f"{name} ({ticker}) — Live Quote",
        publisher="Financial Modeling Prep",
        url=f"https://financialmodelingprep.com/financial-summary/{ticker}",
        retrieved_at=_now(),
        excerpt="; ".join(excerpt_parts) or "No price data available",
        ticker=ticker,
        validation_status=ValidationStatus.RETRIEVED,
    )


# ── 3. FMP company profile ────────────────────────────────────────────────────

def _retrieve_profile(ticker: str, api_key: str) -> Optional[Source]:
    data = _fmp_get(f"/profile/{ticker}", api_key)
    if not data:
        return None
    profile = data[0] if isinstance(data, list) else data
    desc = _truncate(profile.get("description") or "", 400)
    name = profile.get("companyName") or ticker
    industry  = profile.get("industry") or ""
    sector    = profile.get("sector") or ""
    employees = profile.get("fullTimeEmployees")

    parts = []
    if industry:
        parts.append(f"Industry: {industry}")
    if sector:
        parts.append(f"Sector: {sector}")
    if employees:
        parts.append(f"Employees: {employees:,}" if isinstance(employees, int) else f"Employees: {employees}")
    if desc:
        parts.append(desc)

    return Source(
        id=_next_id(),
        source_type=SourceType.PROFILE_DATA,
        title=f"{name} — Company Profile",
        publisher="Financial Modeling Prep",
        url=f"https://financialmodelingprep.com/financial-summary/{ticker}",
        retrieved_at=_now(),
        excerpt="; ".join(parts) or "Profile data unavailable",
        ticker=ticker,
        validation_status=ValidationStatus.RETRIEVED,
    )


# ── 4. FMP financial statements ───────────────────────────────────────────────

def _retrieve_financials(ticker: str, api_key: str) -> List[Source]:
    """Return income + cashflow Sources for the latest 2 reported periods."""
    sources: List[Source] = []

    income_raw = _fmp_get(f"/income-statement/{ticker}?period=annual&limit=10", api_key)
    if income_raw and isinstance(income_raw, list):
        for row in income_raw[:2]:
            period = row.get("calendarYear") or str(row.get("date", ""))[:4]
            rev    = _fmt_large(row.get("revenue"))
            ni     = _fmt_large(row.get("netIncome"))
            ebitda = _fmt_large(row.get("ebitda"))
            gm_pct = _safe_float(row.get("grossProfitRatio"))
            op_pct = _safe_float(row.get("operatingIncomeRatio"))
            ni_pct = _safe_float(row.get("netIncomeRatio"))

            parts = [f"Revenue: {rev}", f"Net income: {ni}", f"EBITDA: {ebitda}"]
            if gm_pct is not None:
                parts.append(f"Gross margin: {gm_pct*100:.1f}%")
            if op_pct is not None:
                parts.append(f"Op margin: {op_pct*100:.1f}%")
            if ni_pct is not None:
                parts.append(f"Net margin: {ni_pct*100:.1f}%")

            sources.append(Source(
                id=_next_id(),
                source_type=SourceType.FINANCIAL_STATEMENT,
                title=f"{ticker} Income Statement — {period}",
                publisher="Financial Modeling Prep",
                url=f"https://financialmodelingprep.com/financial-statements/{ticker}",
                retrieved_at=_now(),
                excerpt="; ".join(parts),
                ticker=ticker,
                reporting_period=f"FY{period}",
                validation_status=ValidationStatus.RETRIEVED,
            ))

    cashflow_raw = _fmp_get(f"/cash-flow-statement/{ticker}?period=annual&limit=10", api_key)
    if cashflow_raw and isinstance(cashflow_raw, list):
        for row in cashflow_raw[:2]:
            period = row.get("calendarYear") or str(row.get("date", ""))[:4]
            ocf    = _fmt_large(row.get("operatingCashFlow"))
            fcf    = _fmt_large(row.get("freeCashFlow"))
            capex  = _fmt_large(row.get("capitalExpenditure"))
            div    = _fmt_large(row.get("dividendsPaid"))
            bback  = _fmt_large(row.get("commonStockRepurchased"))

            parts = [f"Operating CF: {ocf}", f"Free CF: {fcf}", f"CapEx: {capex}"]
            if div and div != "$0.00":
                parts.append(f"Dividends paid: {div}")
            if bback and bback != "$0.00":
                parts.append(f"Buybacks: {bback}")

            sources.append(Source(
                id=_next_id(),
                source_type=SourceType.FINANCIAL_STATEMENT,
                title=f"{ticker} Cash Flow Statement — {period}",
                publisher="Financial Modeling Prep",
                url=f"https://financialmodelingprep.com/financial-statements/{ticker}",
                retrieved_at=_now(),
                excerpt="; ".join(parts),
                ticker=ticker,
                reporting_period=f"FY{period}",
                validation_status=ValidationStatus.RETRIEVED,
            ))

    return sources


# ── 5. Build financial facts dict (for calculator node) ──────────────────────

def _build_financial_facts(ticker: str, api_key: str) -> Dict[str, Any]:
    """Raw numeric dict for deterministic calculations."""
    facts: Dict[str, Any] = {}

    income_raw = _fmp_get(f"/income-statement/{ticker}?period=annual&limit=10", api_key)
    if income_raw and isinstance(income_raw, list) and len(income_raw) >= 1:
        rows = income_raw  # newest first
        facts["income"] = [
            {
                "year":            (r.get("calendarYear") or str(r.get("date", ""))[:4]),
                "revenue":         _safe_float(r.get("revenue")),
                "gross_profit":    _safe_float(r.get("grossProfit")),
                "operating_income":_safe_float(r.get("operatingIncome")),
                "net_income":      _safe_float(r.get("netIncome")),
                "ebitda":          _safe_float(r.get("ebitda")),
                "gross_margin":    _safe_float(r.get("grossProfitRatio")),
                "op_margin":       _safe_float(r.get("operatingIncomeRatio")),
                "net_margin":      _safe_float(r.get("netIncomeRatio")),
                "eps":             _safe_float(r.get("eps")),
            }
            for r in rows[:3]
        ]

    # Current price for return calculations
    quote_data = _fmp_get(f"/quote/{ticker}", api_key)
    if quote_data:
        q = quote_data[0] if isinstance(quote_data, list) else quote_data
        facts["price"]        = _safe_float(q.get("price"))
        facts["year_high"]    = _safe_float(q.get("yearHigh"))
        facts["year_low"]     = _safe_float(q.get("yearLow"))
        facts["change_pct"]   = _safe_float(q.get("changesPercentage"))
        facts["market_cap"]   = _safe_float(q.get("marketCap"))

    return facts


# ── Main retrieval node ───────────────────────────────────────────────────────

def retrieve_evidence(state: CopilotState) -> CopilotState:
    """LangGraph node: retrieve all evidence, return updated state."""
    _reset_counter()

    ticker    = (state.ticker or "").upper()
    question  = state.question or ""
    fmp_key   = os.getenv("FMP_API_KEY", "")
    tav_key   = os.getenv("TAVILY_API_KEY", "")
    sources:  List[Source] = []
    warnings: List[str]    = []

    # 1. News
    news_sources = _retrieve_news(ticker, question, tav_key)
    sources.extend(news_sources)
    if not news_sources:
        warnings.append("News retrieval unavailable — answer based on financial data only.")

    # 2. Market data
    if fmp_key:
        mkt = _retrieve_market_data(ticker, fmp_key)
        if mkt:
            sources.append(mkt)
        else:
            warnings.append(f"Live price data unavailable for {ticker}.")

        # 3. Profile
        prof = _retrieve_profile(ticker, fmp_key)
        if prof:
            sources.append(prof)

        # 4. Financial statements
        fin_sources = _retrieve_financials(ticker, fmp_key)
        sources.extend(fin_sources)
        if not fin_sources:
            warnings.append(f"Financial statement data unavailable for {ticker}.")

        # 5. Raw facts for calculator
        facts = _build_financial_facts(ticker, fmp_key)
    else:
        warnings.append("Financial data unavailable — FMP API key not configured.")
        facts = {}

    # Existing warnings + new ones
    existing = list(state.raw_data_warnings or [])
    existing.extend(warnings)

    return CopilotState(
        **{
            **state.model_dump(),
            "sources": sources,
            "financial_facts": facts,
            "raw_data_warnings": existing,
        }
    )
