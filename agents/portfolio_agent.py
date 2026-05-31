import requests
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
import os, json, re

def get_stock_data(symbol):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=3mo"
        r = requests.get(url, headers=headers, timeout=10).json()
        meta = r["chart"]["result"][0]["meta"]
        closes = r["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        closes = [x for x in closes if x is not None]
        perf = round(((closes[-1] - closes[0]) / closes[0]) * 100, 2) if closes[0] else 0
        curr = meta.get("regularMarketPrice", closes[-1] if closes else 0)
        high = meta.get("fiftyTwoWeekHigh", curr)
        drawdown = round(((curr - high) / high) * 100, 2) if high else 0
        return {
            "symbol": symbol,
            "name": meta.get("longName", symbol),
            "current_price": round(curr, 2),
            "perf_3mo": f"{perf}%",
            "drawdown": f"{drawdown}%",
            "52w_high": high,
            "closes": closes[-30:]
        }
    except Exception as e:
        return {"symbol": symbol, "error": str(e), "closes": []}

def portfolio_agent(state: dict) -> dict:
    holdings = state.get("holdings", [])
    
    stocks = []
    for h in holdings:
        data = get_stock_data(h["symbol"])
        data["allocation"] = h.get("allocation", 0)
        data["shares"]     = h.get("shares", 0)
        stocks.append(data)

    llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"))
    prompt = f"""You are a portfolio manager. Analyse this portfolio and give recommendations.

Portfolio: {json.dumps(stocks, indent=2)}

Return ONLY JSON:
{{
  "overall_score": 7.5,
  "overall_rating": "Good/Average/Poor",
  "risk_level": "Low/Medium/High",
  "diversification_score": 8.0,
  "summary": "3 sentence portfolio summary",
  "best_performer": "TICKER",
  "worst_performer": "TICKER",
  "recommendations": ["action1", "action2", "action3"],
  "rebalancing_needed": true
}}"""
    
    response = llm.invoke([HumanMessage(content=prompt)])
    match = re.search(r'\{.*\}', response.content, re.DOTALL)
    analysis = json.loads(match.group()) if match else {"overall_score": 5, "summary": "Analysis unavailable"}
    
    return {**state, "portfolio": {"stocks": stocks, "analysis": analysis}}