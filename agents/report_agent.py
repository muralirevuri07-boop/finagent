from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
import os, json, re

def report_agent(state: dict) -> dict:
    try:
        llm = ChatGroq(model="openai/gpt-oss-120b", api_key=os.getenv("GROQ_API_KEY"))

        rag_context = state.get("rag_context", {})
        historical  = rag_context.get("historical_news", [])
        has_history = rag_context.get("has_history", False)
        total_stored = rag_context.get("total_stored", 0)

        rag_section = ""
        if has_history and historical:
            rag_section = f"""
HISTORICAL CONTEXT FROM VECTOR DATABASE ({total_stored} articles stored):
{chr(10).join([f"- {doc[:300]}" for doc in historical])}

Use this historical context to provide a more informed analysis.
"""

        prompt = f"""You are a senior financial analyst with access to historical data via RAG.

Ticker: {state["ticker"]}
Market: {state.get("market","US")}
Sentiment: {state["sentiment"]}
Financial Data: {state["financial_data"]}
{rag_section}

Return ONLY valid JSON, no markdown, no code blocks:
{{
  "recommendation": "BUY/HOLD/SELL",
  "confidence": "High/Medium/Low",
  "target_price": 0,
  "reasoning": "3-4 sentence explanation",
  "risks": ["risk1", "risk2"],
  "news_summary": "2 sentence news summary",
  "rag_insight": "1 sentence about what historical data reveals"
}}"""

        response = llm.invoke([HumanMessage(content=prompt)])
        raw = response.content
        raw = re.sub(r"```(?:json)?\s*", "", raw).strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        report = json.loads(match.group()) if match else {
            "recommendation": "HOLD", "confidence": "Low", "target_price": 0,
            "reasoning": "Parse failed.", "risks": ["Unavailable"],
            "news_summary": "No summary.", "rag_insight": "No data."
        }
    except Exception as e:
        report = {
            "recommendation": "HOLD", "confidence": "Low", "target_price": 0,
            "reasoning": f"Error: {str(e)[:200]}", "risks": ["Analysis unavailable"],
            "news_summary": "Unable to generate report.", "rag_insight": "No historical data."
        }
    return {**state, "report": report}
