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


def get_fundamentals(symbol, market):
    """Fetch fundamentals via yfinance. Returns dict with N/A for missing fields."""
    if market in NON_EQUITY_MARKETS:
        return {}
    try:
        t    = yf.Ticker(symbol)
        info = t.info or {}

        # Income statement — annual
        try:
            fin   = t.financials
            rev   = None if fin is None or fin.empty else fin.loc["Total Revenue"].dropna()
            eps_h = None if fin is None or fin.empty else fin.loc["Diluted EPS"].dropna() if "Diluted EPS" in fin.index else None
        except Exception:
            rev, eps_h = None, None

        # Cash flow
        try:
            cf  = t.cashflow
            fcf = None if cf is None or cf.empty else (
                cf.loc["Free Cash Flow"].dropna()
                if "Free Cash Flow" in cf.index else None
            )
        except Exception:
            fcf = None

        # Revenue history (last 4 years)
        rev_history = []
        if rev is not None and len(rev) > 0:
            for date, val in rev.items():
                rev_history.append({
                    "year":    date.year if hasattr(date, "year") else str(date)[:4],
                    "revenue": _fmt_large(val),
                    "raw":     float(val) if val else 0,
                })
            rev_history = sorted(rev_history, key=lambda x: x["year"])

        # FCF history
        fcf_history = []
        if fcf is not None and len(fcf) > 0:
            for date, val in fcf.items():
                fcf_history.append({
                    "year": date.year if hasattr(date, "year") else str(date)[:4],
                    "fcf":  _fmt_large(val),
                    "raw":  float(val) if val else 0,
                })
            fcf_history = sorted(fcf_history, key=lambda x: x["year"])

        return {
            # Valuation
            "pe_ratio":         _safe(info.get("trailingPE")),
            "forward_pe":       _safe(info.get("forwardPE")),
            "price_to_book":    _safe(info.get("priceToBook")),
            "ev_to_ebitda":     _safe(info.get("enterpriseToEbitda")),
            # Size
            "market_cap":       _fmt_large(info.get("marketCap")),
            "enterprise_value": _fmt_large(info.get("enterpriseValue")),
            # Earnings
            "eps_ttm":          _safe(info.get("trailingEps")),
            "eps_forward":      _safe(info.get("forwardEps")),
            "revenue_ttm":      _fmt_large(info.get("totalRevenue")),
            "revenue_growth":   f"{round(info.get('revenueGrowth',0)*100,1)}%"
                                if info.get("revenueGrowth") is not None else "N/A",
            "earnings_growth":  f"{round(info.get('earningsGrowth',0)*100,1)}%"
                                if info.get("earningsGrowth") is not None else "N/A",
            # Margins
            "gross_margin":     f"{round(info.get('grossMargins',0)*100,1)}%"
                                if info.get("grossMargins") is not None else "N/A",
            "operating_margin": f"{round(info.get('operatingMargins',0)*100,1)}%"
                                if info.get("operatingMargins") is not None else "N/A",
            "net_margin":       f"{round(info.get('profitMargins',0)*100,1)}%"
                                if info.get("profitMargins") is not None else "N/A",
            # Balance sheet
            "total_cash":       _fmt_large(info.get("totalCash")),
            "total_debt":       _fmt_large(info.get("totalDebt")),
            "free_cashflow":    _fmt_large(info.get("freeCashflow")),
            "dividend_yield":   f"{round(info.get('dividendYield',0)*100,2)}%"
                                if info.get("dividendYield") else "N/A",
            "beta":             _safe(info.get("beta")),
            "sector":           info.get("sector",  "N/A"),
            "industry":         info.get("industry","N/A"),
            # Histories for valuation engine
            "revenue_history":  rev_history,
            "fcf_history":      fcf_history,
            "shares_outstanding": _safe(info.get("sharesOutstanding"), 0),
            "total_cash_raw":   float(info.get("totalCash") or 0),
            "total_debt_raw":   float(info.get("totalDebt") or 0),
            "current_price_raw": float(info.get("currentPrice") or 0),
        }
    except Exception as e:
        return {"fundamentals_error": str(e)}


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
