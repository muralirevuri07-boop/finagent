import chromadb
from chromadb.utils import embedding_functions
from datetime import datetime

chroma_client = chromadb.PersistentClient(path="./chroma_db")
_embedding_fn = None

def get_embedding_function():
    global _embedding_fn
    if _embedding_fn is None:
        _embedding_fn = embedding_functions.ONNXMiniLM_L6_V2()
    return _embedding_fn

def get_collection(ticker):
    name = "news_" + ticker.replace("-", "_").replace(".", "_").lower()
    return chroma_client.get_or_create_collection(
        name=name,
        embedding_function=get_embedding_function(),
        metadata={"hnsw:space": "cosine"}
    )

def store_news(ticker, articles):
    collection = get_collection(ticker)
    timestamp = datetime.now().isoformat()
    documents, ids, metadatas = [], [], []
    for i, article in enumerate(articles):
        if article and len(article) > 50:
            documents.append(article[:2000])
            ids.append(ticker + "_" + timestamp + "_" + str(i))
            metadatas.append({"ticker": ticker, "timestamp": timestamp, "index": i})
    if documents:
        collection.add(documents=documents, ids=ids, metadatas=metadatas)
    return len(documents)

def retrieve_context(ticker, query, n_results=3):
    collection = get_collection(ticker)
    count = collection.count()
    if count == 0:
        return [], 0
    results = collection.query(query_texts=[query], n_results=min(n_results, count))
    docs = results["documents"][0] if results["documents"] else []
    return docs, count

def rag_agent(state: dict) -> dict:
    ticker = state["ticker"]
    market = state.get("market", "US")
    news = state.get("news", [])
    stored = store_news(ticker, news)
    query = f"{ticker} stock performance analysis outlook {market}"
    historical_docs, total_docs = retrieve_context(ticker, query)
    rag_context = {
        "historical_news": historical_docs,
        "total_stored": total_docs,
        "freshly_stored": stored,
        "has_history": total_docs > 0
    }
    return {**state, "rag_context": rag_context}
