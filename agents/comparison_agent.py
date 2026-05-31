import requests
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
import os, json, re

def get_price_data(symbol):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1mo"
        r = requests.get(url, headers=headers, timeout=10).json()
        meta = r["chart"]["result"][0]["meta"]
        closes = r["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        closes = [x for x in closes if x is not None]
        prev = meta.get("chartPreviousClose", closes[-1])
        curr = meta.get("regularMarketPrice", closes[-1])
        change = round(((curr - prev) / prev) * 100, 2) if prev else 0
        perf_1mo = round(((closes[-1] - closes[0]) / closes[0]) * 100, 2) if closes[0] else 0
        return {
            "symbol": symbol,
            "name": meta.get("longName", symbol),
            "price": round(curr, 2),
            "change": f"{change}%",
            "52w_high": meta.get("fiftyTwoWeekHigh", "N/A"),
            "52w_low": meta.get("fiftyTwoWeekLow", "N/A"),
            "volume": meta.get("regularMarketVolume", "N/A"),
            "perf_1mo": f"{perf_1mo}%",
            "closes": closes
        }
    except Exception as e:
        return {"symbol": symbol, "error": str(e), "closes": []}

def comparison_agent(state: dict) -> dict:
    tickers = state.get("tickers", [])
    market  = state.get("market", "US")
    
    suffix_map = {"NSE":".NS","BSE":".BO","LSE":".L","Frankfurt":".DE","Tokyo":".T","HongKong":".HK","Singapore":".SI"}
    suffix = suffix_map.get(market, "")
    
    stocks = [get_price_data(f"{t}{suffix}") for t in tickers]
    
    llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"))
    prompt = f"""You are a senior analyst. Compare these stocks and pick the best investment.

Stocks data: {json.dumps(stocks, indent=2)}

Return ONLY JSON:
{{
  "winner": "TICKER",
  "winner_reason": "2 sentence explanation",
  "rankings": [{{"ticker":"X","score":8.5,"strength":"...","weakness":"..."}}],
  "summary": "3 sentence comparison summary"
}}"""
    
    response = llm.invoke([HumanMessage(content=prompt)])
    match = re.search(r'\{.*\}', response.content, re.DOTALL)
    analysis = json.loads(match.group()) if match else {"winner": tickers[0], "summary": "Analysis unavailable"}
    
    return {**state, "comparison": {"stocks": stocks, "analysis": analysis}}