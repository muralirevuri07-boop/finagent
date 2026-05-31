from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import List
import sys, os
from tavily import TavilyClient

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from graph.finagent_graph import finagent
from agents.feargreed_agent import feargreed_agent
from agents.comparison_agent import comparison_agent
from agents.portfolio_agent import portfolio_agent
from agents.rag_agent import get_collection

app = FastAPI(title="FinAgent Global API")

class AnalyseRequest(BaseModel):
    ticker: str
    market: str = "US"

class CompareRequest(BaseModel):
    tickers: List[str]
    market: str = "US"

class Holding(BaseModel):
    symbol: str
    allocation: float = 0
    shares: float = 0

class PortfolioRequest(BaseModel):
    holdings: List[Holding]

@app.post("/analyse")
async def analyse(req: AnalyseRequest):
    initial_state = {
        "ticker": req.ticker.upper(),
        "market": req.market,
        "news": [], "sentiment": {}, "financial_data": {}, "report": {}, "rag_context": {}
    }
    result = finagent.invoke(initial_state)
    return {
        "ticker": result["ticker"],
        "market": result["market"],
        "sentiment": result["sentiment"],
        "financial_data": result["financial_data"],
        "report": result["report"],
        "rag_context": result["rag_context"]
    }

@app.get("/feargreed")
async def fear_greed():
    result = feargreed_agent({})
    return result["feargreed"]

@app.post("/compare")
async def compare(req: CompareRequest):
    state = {"tickers": [t.upper() for t in req.tickers], "market": req.market}
    result = comparison_agent(state)
    return result["comparison"]

@app.post("/portfolio")
async def portfolio(req: PortfolioRequest):
    holdings = [{"symbol": h.symbol.upper(), "allocation": h.allocation, "shares": h.shares} for h in req.holdings]
    result = portfolio_agent({"holdings": holdings})
    return result["portfolio"]

@app.get("/rag/stats/{ticker}")
async def rag_stats(ticker: str):
    try:
        collection = get_collection(ticker.upper())
        return {"ticker": ticker.upper(), "total_embeddings": collection.count(), "status": "active"}
    except Exception as e:
        return {"ticker": ticker.upper(), "total_embeddings": 0, "status": str(e)}
@app.get("/news/general")
async def general_news():
    try:
        client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        results = client.search(
            query="international business markets finance news today 2026",
            max_results=8,
            search_depth="basic"
        )
        news = []
        for r in results["results"]:
            news.append({
                "title": r.get("title",""),
                "url": r.get("url",""),
                "content": r.get("content","")[:150] + "...",
                "source": r.get("url","").split("/")[2].replace("www.","")
            })
        return {"news": news}
    except Exception as e:
        return {"news": [], "error": str(e)}

@app.get("/news/{ticker}")
async def stock_news(ticker: str):
    try:
        client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        results = client.search(
            query=f"{ticker} stock market news analysis 2026",
            max_results=6,
            search_depth="basic"
        )
        news = []
        for r in results["results"]:
            news.append({
                "title": r.get("title",""),
                "url": r.get("url",""),
                "content": r.get("content","")[:150] + "...",
                "source": r.get("url","").split("/")[2].replace("www.","")
            })
        return {"news": news, "ticker": ticker}
    except Exception as e:
        return {"news": [], "error": str(e)}
@app.get("/health")
def health():
    return {"status": "FinAgent Global running 🚀"}