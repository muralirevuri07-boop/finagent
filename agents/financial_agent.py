import requests
import yfinance as yf
from datetime import datetime

MARKET_CONFIG = {
    "US":        {"suffix": "",     "currency": "$",   "label": "🇺🇸 US"},
    "NSE":       {"suffix": ".NS",  "currency": "₹",   "label": "🇮🇳 NSE"},
    "BSE":       {"suffix": ".BO",  "currency": "₹",   "label": "🇮🇳 BSE"},
    "LSE":       {"suffix": ".L",   "currency": "£",   "label": "🇬🇧 LSE"},
    "Frankfurt": {"suffix": ".DE",  "currency": "€",   "label": "🇩🇪 Frankfurt"},
    "Tokyo":     {"suffix": ".T",   "currency": "¥",   "label": "🇯🇵 Tokyo"},
    "HongKong":  {"suffix": ".HK",  "currency": "HK$", "label": "🇭🇰 HK"},
    "Singapore": {"suffix": ".SI",  "currency": "S$",  "label": "🇸🇬 SGX"},
    "Crypto":    {"suffix": "",     "currency": "$",   "label": "₿ Crypto"},
    "Forex":     {"suffix": "",     "currency": "",    "label": "💱 Forex"},
    "Commodity": {"suffix": "",     "currency": "$",   "label": "🏅 Commodity"},
}

NON_EQUITY_MARKETS = {"Crypto", "Forex", "Commodity"}


def _fmt_large(value):
    """Format large numbers: 1.23T, 456.7B, 12.3M"""
    try:
        v = float(value)
        if v >= 1e12:
            return f"{v/1e12:.2f}T"
        if v >= 1e9:
            return f"{v/1e9:.2f}B"
        if v >= 1e6:
            return f"{v/1e6:.2f}M"
        return f"{v:,.0f}"
    except Exception:
        return "N/A"


def _safe(value, decimals=2):
    """Return rounded float or N/A."""
    try:
        if value is None:
            return "N/A"
        f = float(value)
        if f != f:  # NaN check
            return "N/A"
        return round(f, decimals)
    except Exception:
        return "N/A"


def get_yahoo_chart(symbol):
    """Fetch price/OHLC data from Yahoo Finance chart API."""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/"
            f"{symbol}?interval=1d&range=1mo&includePrePost=false"
        )
        r = requests.get(url, headers=headers, timeout=10).json()
        result = r["chart"]["result"][0]
        meta   = result["meta"]
        quotes = result["indicators"]["quote"][0]

        def clean(lst):
            return [round(float(x), 4) if x is not None else None for x in lst]

        closes_clean  = clean(quotes.get("close",  []))
        price_history = [x for x in closes_clean if x is not None]
        prev_close    = meta.get("chartPreviousClose", 0)
        current       = meta.get("regularMarketPrice", 0)
        change_pct    = (
            round(((current - prev_close) / prev_close) * 100, 2)
            if prev_close else "N/A"
        )

        return {
            "current_price":  round(current, 4),
            "change_percent": f"{change_pct}%",
            "52w_high":       meta.get("fiftyTwoWeekHigh",    "N/A"),
            "52w_low":        meta.get("fiftyTwoWeekLow",     "N/A"),
            "day_high":       meta.get("regularMarketDayHigh","N/A"),
            "day_low":        meta.get("regularMarketDayLow", "N/A"),
            "volume":         meta.get("regularMarketVolume", "N/A"),
            "company_name":   meta.get("longName", symbol),
            "price_history":  price_history,
            "ohlc": {
                "open":   clean(quotes.get("open",   [])),
                "high":   clean(quotes.get("high",   [])),
                "low":    clean(quotes.get("low",    [])),
                "close":  closes_clean,
                "volume": [int(v) if v is not None else 0
                           for v in quotes.get("volume", [])],
            },
        }
    except Exception as e:
        return {"error": str(e), "price_history": [], "ohlc": {}}


def _fetch_yahoo_summary(symbol: str) -> dict:
    """
    Fetch fundamentals directly from Yahoo Finance quoteSummary API.
    More reliable than yf.Ticker().info which often returns empty on cloud IPs.
    """
    modules = "price,summaryDetail,defaultKeyStatistics,financialData,assetProfile,incomeStatementHistory,cashflowStatementHistory"
    url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}?modules={modules}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://finance.yahoo.com/",
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        data = r.json()
        result = data.get("quoteSummary", {}).get("result", [])
        if not result:
            return {}
        return result[0]
    except Exception:
        return {}


def _fetch_yahoo_summary_v11(symbol: str) -> dict:
    """Fallback using v11 endpoint."""
    modules = "price,summaryDetail,defaultKeyStatistics,financialData,assetProfile"
    url = f"https://query1.finance.yahoo.com/v11/finance/quoteSummary/{symbol}?modules={modules}"
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        data = r.json()
        result = data.get("quoteSummary", {}).get("result", [])
        return result[0] if result else {}
    except Exception:
        return {}


def _fetch_yahoo_v7_quote(symbol: str) -> dict:
    """
    Fetch fundamentals from Yahoo Finance v7 quote endpoint.
    This is the same endpoint Yahoo Finance's own website uses — very reliable.
    Returns a flat dict of fundamental fields.
    """
    fields = ",".join([
        "regularMarketPrice", "marketCap", "trailingPE", "forwardPE",
        "trailingEps", "forwardEps", "priceToBook", "bookValue",
        "enterpriseValue", "enterpriseToEbitda", "fiftyDayAverage",
        "beta", "dividendYield", "totalRevenue", "grossMargins",
        "operatingMargins", "profitMargins", "freeCashflow",
        "totalCash", "totalDebt", "sharesOutstanding",
        "revenueGrowth", "earningsGrowth", "sector", "industry",
        "longName", "shortName",
    ])
    for host in ["query1", "query2"]:
        url = f"https://{host}.finance.yahoo.com/v7/finance/quote?symbols={symbol}&fields={fields}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://finance.yahoo.com/",
        }
        try:
            r = requests.get(url, headers=headers, timeout=12)
            data = r.json()
            results = data.get("quoteResponse", {}).get("result", [])
            if results:
                return results[0]
        except Exception:
            continue
    return {}


def _safe_mod(module: dict, key: str, fmt="raw"):
    """Safely extract a value from a Yahoo quoteSummary module field."""
    try:
        field = module.get(key, {})
        if isinstance(field, dict):
            return field.get(fmt) or field.get("raw")
        return field
    except Exception:
        return None


def get_fundamentals(symbol, market):
    """Fetch fundamentals via Yahoo Finance quoteSummary API (direct HTTP).
    Falls back to yfinance if API returns empty."""
    if market in NON_EQUITY_MARKETS:
        return {}

    # ── Primary: Yahoo Finance v7/quote (fastest, same as Yahoo website) ─────
    v7 = _fetch_yahoo_v7_quote(symbol)

    # ── Secondary: quoteSummary for deeper data (income/cashflow history) ────
    summary = _fetch_yahoo_summary(symbol)
    if not summary:
        summary = _fetch_yahoo_summary_v11(symbol)

    price_mod    = summary.get("price", {})
    fin_data_mod = summary.get("financialData", {})
    key_stats    = summary.get("defaultKeyStatistics", {})
    summary_det  = summary.get("summaryDetail", {})
    profile_mod  = summary.get("assetProfile", {})
    is_hist      = summary.get("incomeStatementHistory", {}).get("incomeStatementHistory", [])
    cf_hist      = summary.get("cashflowStatementHistory", {}).get("cashflowStatementHistoryItems", []) or \
                   summary.get("cashflowStatementHistory", {}).get("cashflowStatements", [])

    # Revenue history from income statement
    rev_history = []
    try:
        for stmt in is_hist:
            yr = stmt.get("endDate", {}).get("fmt", "")[:4]
            val = _safe_mod(stmt, "totalRevenue") or 0
            if yr and val:
                rev_history.append({"year": int(yr), "revenue": _fmt_large(val), "raw": float(val)})
        rev_history = sorted(rev_history, key=lambda x: x["year"])
    except Exception:
        rev_history = []

    # FCF history from cash flow statement
    fcf_history = []
    try:
        for stmt in cf_hist:
            yr = stmt.get("endDate", {}).get("fmt", "")[:4]
            fcf_val = _safe_mod(stmt, "freeCashflow") or 0
            if not fcf_val:
                ops = _safe_mod(stmt, "totalCashFromOperatingActivities") or 0
                cap = _safe_mod(stmt, "capitalExpenditures") or 0
                fcf_val = ops + cap  # capex is usually negative
            if yr and fcf_val:
                fcf_history.append({"year": int(yr), "fcf": _fmt_large(fcf_val), "raw": float(fcf_val)})
        fcf_history = sorted(fcf_history, key=lambda x: x["year"])
    except Exception:
        fcf_history = []

    # ── If v7 has data and quoteSummary is empty, build from v7 ─────────────
    if v7 and not price_mod and not fin_data_mod:
        def pct_v7(key):
            v = v7.get(key)
            return f"{round(float(v)*100, 1)}%" if v is not None else "N/A"

        shares_v7 = v7.get("sharesOutstanding")
        cash_v7   = v7.get("totalCash")
        debt_v7   = v7.get("totalDebt")
        fcf_v7    = v7.get("freeCashflow")

        return {
            "pe_ratio":         _safe(v7.get("trailingPE")),
            "forward_pe":       _safe(v7.get("forwardPE")),
            "price_to_book":    _safe(v7.get("priceToBook")),
            "ev_to_ebitda":     _safe(v7.get("enterpriseToEbitda")),
            "market_cap":       _fmt_large(v7.get("marketCap")),
            "enterprise_value": _fmt_large(v7.get("enterpriseValue")),
            "eps_ttm":          _safe(v7.get("trailingEps")),
            "eps_forward":      _safe(v7.get("forwardEps")),
            "revenue_ttm":      _fmt_large(v7.get("totalRevenue")),
            "revenue_growth":   pct_v7("revenueGrowth"),
            "earnings_growth":  pct_v7("earningsGrowth"),
            "gross_margin":     pct_v7("grossMargins"),
            "operating_margin": pct_v7("operatingMargins"),
            "net_margin":       pct_v7("profitMargins"),
            "total_cash":       _fmt_large(cash_v7),
            "total_debt":       _fmt_large(debt_v7),
            "free_cashflow":    _fmt_large(fcf_v7),
            "dividend_yield":   pct_v7("dividendYield"),
            "beta":             _safe(v7.get("beta")),
            "sector":           v7.get("sector", "N/A"),
            "industry":         v7.get("industry", "N/A"),
            "revenue_history":  rev_history,
            "fcf_history":      fcf_history,
            "shares_outstanding": _safe(shares_v7, 0),
            "total_cash_raw":   float(cash_v7 or 0),
            "total_debt_raw":   float(debt_v7 or 0),
            "current_price_raw": float(v7.get("regularMarketPrice") or 0),
        }

    # ── If direct API totally empty, fallback to yfinance ────────────────────
    if not price_mod and not fin_data_mod and not v7:
        try:
            t = yf.Ticker(symbol)
            info = t.fast_info if hasattr(t, "fast_info") else {}
            full_info = {}
            try:
                full_info = t.info or {}
            except Exception:
                pass
            info_dict = dict(full_info) if full_info else {}

            if not info_dict:
                return {}

            # Build rev/fcf from yfinance as last resort
            try:
                fin = t.financials
                rev_s = None if fin is None or fin.empty else fin.loc["Total Revenue"].dropna() if "Total Revenue" in fin.index else None
                if rev_s is not None:
                    for date, val in rev_s.items():
                        yr = date.year if hasattr(date, "year") else int(str(date)[:4])
                        rev_history.append({"year": yr, "revenue": _fmt_large(val), "raw": float(val)})
                    rev_history = sorted(rev_history, key=lambda x: x["year"])
            except Exception:
                pass

            try:
                cf = t.cashflow
                fcf_s = None if cf is None or cf.empty else cf.loc["Free Cash Flow"].dropna() if "Free Cash Flow" in cf.index else None
                if fcf_s is not None:
                    for date, val in fcf_s.items():
                        yr = date.year if hasattr(date, "year") else int(str(date)[:4])
                        fcf_history.append({"year": yr, "fcf": _fmt_large(val), "raw": float(val)})
                    fcf_history = sorted(fcf_history, key=lambda x: x["year"])
            except Exception:
                pass

            return {
                "pe_ratio":         _safe(info_dict.get("trailingPE")),
                "forward_pe":       _safe(info_dict.get("forwardPE")),
                "price_to_book":    _safe(info_dict.get("priceToBook")),
                "ev_to_ebitda":     _safe(info_dict.get("enterpriseToEbitda")),
                "market_cap":       _fmt_large(info_dict.get("marketCap")),
                "enterprise_value": _fmt_large(info_dict.get("enterpriseValue")),
                "eps_ttm":          _safe(info_dict.get("trailingEps")),
                "eps_forward":      _safe(info_dict.get("forwardEps")),
                "revenue_ttm":      _fmt_large(info_dict.get("totalRevenue")),
                "revenue_growth":   f"{round(info_dict.get('revenueGrowth',0)*100,1)}%" if info_dict.get("revenueGrowth") is not None else "N/A",
                "earnings_growth":  f"{round(info_dict.get('earningsGrowth',0)*100,1)}%" if info_dict.get("earningsGrowth") is not None else "N/A",
                "gross_margin":     f"{round(info_dict.get('grossMargins',0)*100,1)}%" if info_dict.get("grossMargins") is not None else "N/A",
                "operating_margin": f"{round(info_dict.get('operatingMargins',0)*100,1)}%" if info_dict.get("operatingMargins") is not None else "N/A",
                "net_margin":       f"{round(info_dict.get('profitMargins',0)*100,1)}%" if info_dict.get("profitMargins") is not None else "N/A",
                "total_cash":       _fmt_large(info_dict.get("totalCash")),
                "total_debt":       _fmt_large(info_dict.get("totalDebt")),
                "free_cashflow":    _fmt_large(info_dict.get("freeCashflow")),
                "dividend_yield":   f"{round(info_dict.get('dividendYield',0)*100,2)}%" if info_dict.get("dividendYield") else "N/A",
                "beta":             _safe(info_dict.get("beta")),
                "sector":           info_dict.get("sector", "N/A"),
                "industry":         info_dict.get("industry", "N/A"),
                "revenue_history":  rev_history,
                "fcf_history":      fcf_history,
                "shares_outstanding": _safe(info_dict.get("sharesOutstanding"), 0),
                "total_cash_raw":   float(info_dict.get("totalCash") or 0),
                "total_debt_raw":   float(info_dict.get("totalDebt") or 0),
                "current_price_raw": float(info_dict.get("currentPrice") or 0),
            }
        except Exception as e:
            return {"fundamentals_error": str(e)}

    # ── Extract from quoteSummary + v7 merged ────────────────────────────────
    def pct(mod, key):
        v = _safe_mod(mod, key)
        return f"{round(float(v)*100, 1)}%" if v is not None else "N/A"

    # v7 as a fallback for each field when quoteSummary is empty
    def _first(*vals):
        for v in vals:
            if v is not None and v != "N/A" and v != 0 and v != "0" and v != "":
                return v
        return None

    market_cap_raw = _first(_safe_mod(price_mod, "marketCap"),       v7.get("marketCap"))
    ev_raw         = _first(_safe_mod(key_stats, "enterpriseValue"),  v7.get("enterpriseValue"))
    shares_raw     = _first(_safe_mod(key_stats, "sharesOutstanding"),v7.get("sharesOutstanding"))
    cash_raw       = _first(_safe_mod(fin_data_mod, "totalCash"),     v7.get("totalCash"))
    debt_raw       = _first(_safe_mod(fin_data_mod, "totalDebt"),     v7.get("totalDebt"))
    fcf_raw        = _first(_safe_mod(fin_data_mod, "freeCashflow"),  v7.get("freeCashflow"))

    def pct_first(mod, key, v7key=None):
        v = _safe_mod(mod, key)
        if v is None and v7key:
            v = v7.get(v7key)
        return f"{round(float(v)*100, 1)}%" if v is not None else "N/A"

    return {
        "pe_ratio":         _safe(_first(_safe_mod(summary_det, "trailingPE"), v7.get("trailingPE"))),
        "forward_pe":       _safe(_first(_safe_mod(key_stats, "forwardPE"),    v7.get("forwardPE"))),
        "price_to_book":    _safe(_first(_safe_mod(key_stats, "priceToBook"),  v7.get("priceToBook"))),
        "ev_to_ebitda":     _safe(_first(_safe_mod(key_stats, "enterpriseToEbitda"), v7.get("enterpriseToEbitda"))),
        "market_cap":       _fmt_large(market_cap_raw),
        "enterprise_value": _fmt_large(ev_raw),
        "eps_ttm":          _safe(_first(_safe_mod(key_stats, "trailingEps"),  v7.get("trailingEps"))),
        "eps_forward":      _safe(_first(_safe_mod(key_stats, "forwardEps"),   v7.get("forwardEps"))),
        "revenue_ttm":      _fmt_large(_first(_safe_mod(fin_data_mod, "totalRevenue"), v7.get("totalRevenue"))),
        "revenue_growth":   pct_first(fin_data_mod, "revenueGrowth",   "revenueGrowth"),
        "earnings_growth":  pct_first(fin_data_mod, "earningsGrowth",  "earningsGrowth"),
        "gross_margin":     pct_first(fin_data_mod, "grossMargins",    "grossMargins"),
        "operating_margin": pct_first(fin_data_mod, "operatingMargins","operatingMargins"),
        "net_margin":       pct_first(fin_data_mod, "profitMargins",   "profitMargins"),
        "total_cash":       _fmt_large(cash_raw),
        "total_debt":       _fmt_large(debt_raw),
        "free_cashflow":    _fmt_large(fcf_raw),
        "dividend_yield":   pct_first(summary_det, "dividendYield",    "dividendYield"),
        "beta":             _safe(_first(_safe_mod(summary_det, "beta"), _safe_mod(key_stats, "beta"), v7.get("beta"))),
        "sector":           profile_mod.get("sector") or v7.get("sector", "N/A"),
        "industry":         profile_mod.get("industry") or v7.get("industry", "N/A"),
        # Histories for valuation engine
        "revenue_history":    rev_history,
        "fcf_history":        fcf_history,
        "shares_outstanding": _safe(shares_raw, 0),
        "total_cash_raw":     float(cash_raw or 0),
        "total_debt_raw":     float(debt_raw or 0),
        "current_price_raw":  float(_first(_safe_mod(price_mod, "regularMarketPrice"), v7.get("regularMarketPrice")) or 0),
    }


def financial_agent(state: dict) -> dict:
    ticker = state["ticker"]
    market = state.get("market", "US")
    config = MARKET_CONFIG.get(market, MARKET_CONFIG["US"])
    currency = config["currency"]

    symbol = ticker if market in NON_EQUITY_MARKETS else f"{ticker}{config['suffix']}"

    chart  = get_yahoo_chart(symbol)
    fundas = get_fundamentals(symbol, market)

    data = {
        "ticker":        symbol,
        "currency":      currency,
        "market":        market,
        "market_label":  config["label"],
        "company_name":  chart.get("company_name", symbol),
        "current_price": f"{currency}{chart.get('current_price','N/A')}",
        "current_price_raw": chart.get("current_price", 0),
        "change_percent":    chart.get("change_percent","N/A"),
        "52w_high":  f"{currency}{chart.get('52w_high','N/A')}",
        "52w_low":   f"{currency}{chart.get('52w_low','N/A')}",
        "day_high":  f"{currency}{chart.get('day_high','N/A')}",
        "day_low":   f"{currency}{chart.get('day_low','N/A')}",
        "volume":    chart.get("volume","N/A"),
        "price_history": chart.get("price_history",[]),
        "ohlc":          chart.get("ohlc",{}),
        # Fundamentals (N/A for crypto/forex/commodity)
        "pe_ratio":         fundas.get("pe_ratio",         "N/A"),
        "forward_pe":       fundas.get("forward_pe",       "N/A"),
        "price_to_book":    fundas.get("price_to_book",    "N/A"),
        "ev_to_ebitda":     fundas.get("ev_to_ebitda",     "N/A"),
        "market_cap":       fundas.get("market_cap",       "N/A"),
        "enterprise_value": fundas.get("enterprise_value", "N/A"),
        "eps_ttm":          fundas.get("eps_ttm",          "N/A"),
        "eps_forward":      fundas.get("eps_forward",      "N/A"),
        "revenue_ttm":      fundas.get("revenue_ttm",      "N/A"),
        "revenue_growth":   fundas.get("revenue_growth",   "N/A"),
        "earnings_growth":  fundas.get("earnings_growth",  "N/A"),
        "gross_margin":     fundas.get("gross_margin",     "N/A"),
        "operating_margin": fundas.get("operating_margin", "N/A"),
        "net_margin":       fundas.get("net_margin",       "N/A"),
        "total_cash":       fundas.get("total_cash",       "N/A"),
        "total_debt":       fundas.get("total_debt",       "N/A"),
        "free_cashflow":    fundas.get("free_cashflow",    "N/A"),
        "dividend_yield":   fundas.get("dividend_yield",   "N/A"),
        "beta":             fundas.get("beta",             "N/A"),
        "sector":           fundas.get("sector",           "N/A"),
        "industry":         fundas.get("industry",         "N/A"),
        # Raw data for valuation engine
        "revenue_history":    fundas.get("revenue_history",    []),
        "fcf_history":        fundas.get("fcf_history",        []),
        "shares_outstanding": fundas.get("shares_outstanding", "N/A"),
        "total_cash_raw":     fundas.get("total_cash_raw",     0),
        "total_debt_raw":     fundas.get("total_debt_raw",     0),
        "market":             market,
    }

    return {**state, "financial_data": data}
