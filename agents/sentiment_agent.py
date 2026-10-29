from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
import os, json, re

def sentiment_agent(state: dict) -> dict:
    try:
        llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY"))
        # Truncate each article to 400 chars, take top 8 articles max
        articles = [str(a)[:400] for a in state["news"][:8]]
        news_text = "\n\n".join(articles)
        prompt = f"""Analyse the sentiment of these news articles about {state['ticker']}.
Return ONLY a JSON like: {{"sentiment": "Bullish/Bearish/Neutral", "score": 0.0-1.0, "summary": "2 sentence reason"}}

Articles:
{news_text}"""
        response = llm.invoke([HumanMessage(content=prompt)])
        match = re.search(r'\{.*\}', response.content, re.DOTALL)
        sentiment_data = json.loads(match.group()) if match else {
            "sentiment": "Neutral", "score": 0.5, "summary": "Unable to parse response"
        }
    except Exception as e:
        sentiment_data = {
            "sentiment": "Neutral",
            "score": 0.5,
            "summary": f"Sentiment analysis unavailable: {str(e)[:100]}"
        }
    return {**state, "sentiment": sentiment_data}

