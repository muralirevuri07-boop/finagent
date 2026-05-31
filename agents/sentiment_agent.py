from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
import os
import json
import re

def sentiment_agent(state: dict) -> dict:
    llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"))
    news_text = "\n\n".join(state["news"])
    prompt = f"""Analyse the sentiment of these news articles about {state['ticker']}.
Return ONLY a JSON like: {{"sentiment": "Bullish/Bearish/Neutral", "score": 0.0-1.0, "summary": "2 sentence reason"}}

Articles:
{news_text}"""
    response = llm.invoke([HumanMessage(content=prompt)])
    match = re.search(r'\{.*\}', response.content, re.DOTALL)
    sentiment_data = json.loads(match.group()) if match else {
        "sentiment": "Neutral",
        "score": 0.5,
        "summary": "Unable to analyse"
    }
    return {**state, "sentiment": sentiment_data}