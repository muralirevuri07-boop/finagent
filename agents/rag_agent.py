import os
import chromadb
from chromadb.utils import embedding_functions
from datetime import datetime

# Initialize ChromaDB
chroma_client = chromadb.PersistentClient(path="./chroma_db")
embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

def get_collection(ticker):
    name = "news_" + ticker.replace("-","_").replace(".","_").lower()
    return chroma_client.get_or_create_collection(
        name=name,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"}
    )

def store_news(ticker, articles):
    """Store news articles as embeddings in ChromaDB"""
    collection = get_collection(ticker)
    timestamp = datetime.now().isoformat()
    documents, ids, metadatas = [], [], []
    for i, article in enumerate(articles):
        if article and len(article) > 50:
            doc_id = ticker + "_" + timestamp + "_" + str(i)
            documents.append(article[:2000])
            ids.append(doc_id)
            metadatas.append({"ticker": ticker, "timestamp": timestamp, "index": i})
    if documents:
        collection.add(documents=documents, ids=ids, metadatas=metadatas)
    return len(documents)

def retrieve_context(ticker, query, n_results=3):
    """Retrieve relevant past news for RAG context"""
    collection = get_collection(ticker)
    count = collection.count()
    if count == 0:
        return [], 0
    n = min(n_results, count)
    results = collection.query(query_texts=[query], n_results=n)
    docs = results["documents"][0] if results["documents"] else []
    return docs, count

def rag_agent(state: dict) -> dict:
    ticker = state["ticker"]
    market = state.get("market", "US")
    news   = state.get("news", [])

    # Store fresh news into ChromaDB
    stored = store_news(ticker, news)

    # Retrieve relevant historical context
    query = f"{ticker} stock performance analysis outlook {market}"
    historical_docs, total_docs = retrieve_context(ticker, query)

    rag_context = {
        "historical_news": historical_docs,
        "total_stored": total_docs,
        "freshly_stored": stored,
        "has_history": total_docs > 0
    }

    return {**state, "rag_context": rag_context}