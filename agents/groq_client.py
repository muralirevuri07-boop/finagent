"""
groq_client.py
Shared Groq LLM factory that auto-selects the first working model.

Tries models in order until one responds without a 404/access error.
This avoids hard-coding a single model name that may not be accessible
on the user's current Groq plan.
"""
import os
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

# Ordered by preference: fastest/smallest first, then fallbacks
_CANDIDATE_MODELS = [
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "openai/gpt-oss-20b",
    "qwen/qwen3-32b",
    "gemma2-9b-it",
    "gemma-7b-it",
    "mixtral-8x7b-32768",
    "llama3-8b-8192",
]

_cached_model: str | None = None


def get_groq_llm() -> ChatGroq:
    """
    Return a ChatGroq instance using the first model the current API key can access.
    Result is cached for the process lifetime so we only probe once.
    """
    global _cached_model
    api_key = os.getenv("GROQ_API_KEY", "")

    if _cached_model:
        return ChatGroq(model=_cached_model, api_key=api_key)

    probe = HumanMessage(content="hi")
    for model in _CANDIDATE_MODELS:
        try:
            llm = ChatGroq(model=model, api_key=api_key)
            llm.invoke([probe])          # test call — raises on 404/400
            _cached_model = model
            print(f"[GroqClient] Using model: {model}")
            return llm
        except Exception as e:
            msg = str(e).lower()
            if "404" in msg or "does not exist" in msg or "do not have access" in msg or "400" in msg or "decommissioned" in msg:
                continue          # try next model
            # Other error (rate limit, network) — still use this model
            _cached_model = model
            return ChatGroq(model=model, api_key=api_key)

    # Last resort — return first candidate and let the caller handle the error
    _cached_model = _CANDIDATE_MODELS[0]
    return ChatGroq(model=_CANDIDATE_MODELS[0], api_key=api_key)
