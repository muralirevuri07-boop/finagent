from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Optional
from agents.news_agent import news_agent
from agents.sentiment_agent import sentiment_agent
from agents.financial_agent import financial_agent
from agents.report_agent import report_agent
from agents.rag_agent import rag_agent

class GraphState(TypedDict):
    ticker: str
    market: str
    news: List[str]
    sentiment: dict
    financial_data: dict
    report: dict
    rag_context: dict

def build_graph():
    graph = StateGraph(GraphState)

    graph.add_node("news_scraper",      news_agent)
    graph.add_node("rag_store_retrieve", rag_agent)
    graph.add_node("financial_data",    financial_agent)
    graph.add_node("sentiment_analyser", sentiment_agent)
    graph.add_node("report_generator",  report_agent)

    graph.set_entry_point("news_scraper")
    graph.add_edge("news_scraper",       "rag_store_retrieve")
    graph.add_edge("rag_store_retrieve", "financial_data")
    graph.add_edge("financial_data",     "sentiment_analyser")
    graph.add_edge("sentiment_analyser", "report_generator")
    graph.add_edge("report_generator",   END)

    return graph.compile()

finagent = build_graph()