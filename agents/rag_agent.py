from datetime import datetime

def rag_agent(state: dict) -> dict:
    """RAG disabled on free tier - pipeline runs on live data only."""
    rag_context = {
        "historical_news": [],
        "total_stored": 0,
        "freshly_stored": 0,
        "has_history": False
    }
    return {**state, "rag_context": rag_context}

def store_news(ticker, articles):
    return 0

def retrieve_context(ticker, query, n_results=3):
    return [], 0

def get_collection(ticker):
    return None
