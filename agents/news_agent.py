from tavily import TavilyClient
import os
import urllib.request
import urllib.parse
import json

MARKET_CONTEXT = {
    "US":        "US stock market NYSE NASDAQ",
    "NSE":       "India NSE National Stock Exchange",
    "BSE":       "India BSE Bombay Stock Exchange",
    "LSE":       "London Stock Exchange UK",
    "Frankfurt": "Frankfurt XETRA German stock market",
    "Tokyo":     "Tokyo Stock Exchange Japan TSE",
    "HongKong":  "Hong Kong Stock Exchange HKEX",
    "Singapore": "Singapore Exchange SGX",
    "Crypto":    "cryptocurrency blockchain crypto market",
    "Forex":     "forex foreign exchange currency market",
    "Commodity": "commodities futures market gold oil silver",
}

def _fetch_newsapi(ticker: str, market: str) -> list[str]:
    """NewsAPI.org fallback — returns up to 5 article descriptions."""
    api_key = os.getenv("NEWSAPI_KEY", "")
    if not api_key:
        return []
    context = MARKET_CONTEXT.get(market, "stock market")
    query   = urllib.parse.quote(f"{ticker} {context}")
    url     = (
        f"https://newsapi.org/v2/everything"
        f"?q={query}&sortBy=publishedAt&pageSize=5&language=en"
        f"&apiKey={api_key}"
    )
    try:
        req  = urllib.request.Request(url, headers={"User-Agent": "FinAgent/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        articles = []
        for a in data.get("articles", []):
            title       = a.get("title", "")
            description = a.get("description", "")
            content     = a.get("content", "")
            text = f"{title}. {description} {content}".strip()
            if text and text != ".":
                articles.append(text[:800])
        return articles
    except Exception:
        return []

def news_agent(state: dict) -> dict:
    ticker  = state["ticker"]
    market  = state.get("market", "US")
    context = MARKET_CONTEXT.get(market, "stock market")
    query   = f"{ticker} {context} analysis news 2026"
    articles: list[str] = []

    # --- Primary: Tavily ---
    try:
        client   = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        results  = client.search(query=query, max_results=5, search_depth="advanced")
        articles = [r["content"] for r in results.get("results", []) if r.get("content")]
    except Exception:
        pass

    # --- Fallback: NewsAPI when Tavily returns < 3 results ---
    if len(articles) < 3:
        newsapi_articles = _fetch_newsapi(ticker, market)
        # merge, deduplicate by first 60 chars
        seen    = {a[:60] for a in articles}
        for a in newsapi_articles:
            if a[:60] not in seen:
                articles.append(a)
                seen.add(a[:60])

    # --- Hard fallback: placeholder ---
    if not articles:
        articles = [
            f"Latest market analysis for {ticker} — live news unavailable. "
            "Proceeding with financial data and historical context only."
        ]

    return {**state, "news": articles}
