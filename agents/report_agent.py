from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from agents.valuation_engine import compute_valuation
import os, json, re


def report_agent(state: dict) -> dict:
    # ── 1. Deterministic valuation (LLM-free) ────────────────────────────────
    fin       = state.get("financial_data", {})
    valuation = compute_valuation(fin)

    # ── 2. Build LLM prompt (LLM never produces numbers) ─────────────────────
    rag_context = state.get("rag_context", {})
    historical  = rag_context.get("historical_news", [])
    has_history = rag_context.get("has_history", False)
    total_stored = rag_context.get("total_stored", 0)

    rag_section = ""
    if has_history and historical:
        rag_section = f"""
HISTORICAL CONTEXT FROM RAG ({total_stored} articles stored):
{chr(10).join([f'- {doc[:300]}' for doc in historical])}
Use this historical context to improve the analysis quality.
"""

    # Valuation summary for LLM context
    if valuation["available"]:
        val_summary = (
            f"Bear: {valuation['currency']}{valuation['bear']} | "
            f"Base: {valuation['currency']}{valuation['base']} | "
            f"Bull: {valuation['currency']}{valuation['bull']} "
            f"(Method: {valuation['method']}, "
            f"Upside to base: {valuation['upside_base']})"
        )
    else:
        val_summary = f"Valuation unavailable: {valuation['unavailable_reason']}"

    prompt = f"""You are a senior financial analyst. Your job is to write the QUALITATIVE sections only.
All numerical values are pre-calculated and provided to you — do NOT invent or modify any numbers.

Ticker: {state['ticker']}
Market: {state.get('market','US')}
Sentiment: {state['sentiment']}
Financial Data: {json.dumps(fin, default=str)[:1500]}
Pre-calculated Valuation: {val_summary}
{rag_section}

Write 3-4 sentences of qualitative reasoning that references the fundamentals and valuation.
Then return ONLY this JSON (do not add or change any numbers):
{{
  "recommendation": "BUY/HOLD/SELL",
  "reasoning": "3-4 sentence qualitative explanation referencing the provided fundamentals and valuation",
  "risks": ["risk1", "risk2", "risk3"],
  "news_summary": "2 sentence news summary",
  "rag_insight": "1 sentence about historical data, or 'No historical data available.'"
}}

Rules:
- recommendation must be BUY, HOLD, or SELL based on valuation upside and sentiment
- Do NOT invent target prices or financial ratios — those come from the valuation engine
- If valuation is unavailable, base recommendation on sentiment and fundamentals only"""

    try:
        llm = ChatGroq(model="openai/gpt-oss-120b", api_key=os.getenv("GROQ_API_KEY"))
        response = llm.invoke([HumanMessage(content=prompt)])
        raw   = response.content
        raw   = re.sub(r"```(?:json)?\s*", "", raw).strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        llm_out = json.loads(match.group()) if match else {}
    except Exception as e:
        llm_out = {
            "recommendation": "HOLD",
            "reasoning":      f"Analysis error: {str(e)[:150]}",
            "risks":          ["Data unavailable"],
            "news_summary":   "News analysis unavailable.",
            "rag_insight":    "No historical data available.",
        }

    # ── 3. Assemble final report (valuation numbers are authoritative) ────────
    report = {
        "recommendation":   llm_out.get("recommendation", "HOLD"),
        "confidence":       _confidence(valuation, state.get("sentiment", {})),
        # Valuation targets — from engine, not LLM
        "target_price":     valuation["base"],
        "target_bear":      valuation["bear"],
        "target_bull":      valuation["bull"],
        "valuation_method": valuation["method"],
        "valuation_upside": valuation["upside_base"],
        "valuation_available": valuation["available"],
        "valuation_unavailable_reason": valuation["unavailable_reason"],
        "valuation_assumptions": valuation["assumptions"],
        # Qualitative — from LLM
        "reasoning":    llm_out.get("reasoning",    "Insufficient data."),
        "risks":        llm_out.get("risks",         ["Data unavailable"]),
        "news_summary": llm_out.get("news_summary",  "No news found."),
        "rag_insight":  llm_out.get("rag_insight",   "No historical data available."),
    }

    return {**state, "report": report, "valuation": valuation}


def _confidence(valuation: dict, sentiment: dict) -> str:
    """
    Simple rule-based confidence:
    - High:   valuation available + strong sentiment alignment
    - Medium: valuation available OR sentiment is clear
    - Low:    neither
    """
    has_val = valuation.get("available", False)
    sent    = sentiment.get("sentiment", "Neutral")
    score   = sentiment.get("score", 0.5)

    strong_sentiment = sent in ("Bullish", "Bearish") and (score >= 0.70 or score <= 0.30)

    if has_val and strong_sentiment:
        return "High"
    if has_val or strong_sentiment:
        return "Medium"
    return "Low"
