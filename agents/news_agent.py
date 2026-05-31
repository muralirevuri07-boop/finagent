from tavily import TavilyClient
import os

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

def news_agent(state: dict) -> dict:
    client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    ticker = state["ticker"]
    market = state.get("market", "US")
    context = MARKET_CONTEXT.get(market, "stock market")

    query = f"{ticker} {context} analysis news 2026"

    results = client.search(
        query=query,
        max_results=5,
        search_depth="advanced"
    )
    articles = [r["content"] for r in results["results"]]
    return {**state, "news": articles}