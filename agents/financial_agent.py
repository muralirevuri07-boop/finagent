import requests

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

def get_yahoo_data(symbol):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1mo&includePrePost=false"
        r = requests.get(url, headers=headers, timeout=10).json()
        result = r["chart"]["result"][0]
        meta = result["meta"]
        quotes = result["indicators"]["quote"][0]

        opens   = quotes.get("open",   [])
        highs   = quotes.get("high",   [])
        lows    = quotes.get("low",    [])
        closes  = quotes.get("close",  [])
        volumes = quotes.get("volume", [])

        def clean(lst):
            return [round(float(x), 4) if x is not None else None for x in lst]

        closes_clean = clean(closes)
        price_history = [x for x in closes_clean if x is not None]

        prev_close = meta.get("chartPreviousClose", 0)
        current    = meta.get("regularMarketPrice", 0)
        change_pct = round(((current - prev_close) / prev_close) * 100, 2) if prev_close else "N/A"

        return {
            "current_price": round(current, 4),
            "change_percent": f"{change_pct}%",
            "52w_high":  meta.get("fiftyTwoWeekHigh", "N/A"),
            "52w_low":   meta.get("fiftyTwoWeekLow",  "N/A"),
            "day_high":  meta.get("regularMarketDayHigh", "N/A"),
            "day_low":   meta.get("regularMarketDayLow",  "N/A"),
            "volume":    meta.get("regularMarketVolume",  "N/A"),
            "company_name": meta.get("longName", symbol),
            "price_history": price_history,
            "ohlc": {
                "open":   clean(opens),
                "high":   clean(highs),
                "low":    clean(lows),
                "close":  closes_clean,
                "volume": [int(v) if v is not None else 0 for v in volumes],
            }
        }
    except Exception as e:
        return {"error": str(e), "price_history": [], "ohlc": {}}

def financial_agent(state: dict) -> dict:
    ticker = state["ticker"]
    market = state.get("market", "US")
    config = MARKET_CONFIG.get(market, MARKET_CONFIG["US"])
    currency = config["currency"]

    if market in ["Crypto", "Forex", "Commodity"]:
        symbol = ticker
    else:
        symbol = f"{ticker}{config['suffix']}"

    raw = get_yahoo_data(symbol)

    data = {
        "ticker":        symbol,
        "currency":      currency,
        "market":        market,
        "market_label":  config["label"],
        "company_name":  raw.get("company_name", symbol),
        "current_price": f"{currency}{raw.get('current_price','N/A')}",
        "change_percent":raw.get("change_percent","N/A"),
        "pe_ratio":      "N/A",
        "market_cap":    "N/A",
        "52w_high":      f"{currency}{raw.get('52w_high','N/A')}",
        "52w_low":       f"{currency}{raw.get('52w_low','N/A')}",
        "day_high":      f"{currency}{raw.get('day_high','N/A')}",
        "day_low":       f"{currency}{raw.get('day_low','N/A')}",
        "volume":        raw.get("volume","N/A"),
        "price_history": raw.get("price_history",[]),
        "ohlc":          raw.get("ohlc",{}),
    }

    return {**state, "financial_data": data}