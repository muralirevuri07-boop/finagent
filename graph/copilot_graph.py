"""
copilot_graph.py — LangGraph pipeline for the AI Research Copilot.

Pipeline:
  validate_input → retrieve_evidence → run_calculations → synthesise
    → validate_citations → assemble_response → END

Each node receives and returns CopilotState.  On abort, all nodes downstream
of the abort point are skipped.
"""

from __future__ import annotations
import time
import uuid
from typing import Any, Dict

from langgraph.graph import StateGraph, END

from agents.copilot.evidence_model import (
    CopilotState, CopilotResponse, Claim, Calculation
)
from agents.copilot.evidence_retriever import retrieve_evidence
from agents.copilot.calculator import run_calculations
from agents.copilot.synthesiser import synthesise
from agents.copilot.citation_validator import citation_validator_node


# ── node: validate_input ──────────────────────────────────────────────────────

MAX_QUESTION_LEN = 500


def validate_input(state: CopilotState) -> CopilotState:
    """Sanitise and validate the incoming request."""
    ticker   = (state.ticker or "").strip().upper()
    question = (state.question or "").strip()

    if not ticker:
        return CopilotState(**{**state.model_dump(),
            "aborted": True, "abort_reason": "Ticker is required."})

    if not question:
        return CopilotState(**{**state.model_dump(),
            "aborted": True, "abort_reason": "Question is required."})

    if len(question) > MAX_QUESTION_LEN:
        question = question[:MAX_QUESTION_LEN]

    # Reject obvious prompt-injection attempts in the question itself
    _INJECTION_SIGNALS = [
        "ignore previous instructions",
        "ignore prior instructions",
        "forget your instructions",
        "new instructions:",
        "system prompt:",
        "you are now",
        "act as",
    ]
    lower_q = question.lower()
    for signal in _INJECTION_SIGNALS:
        if signal in lower_q:
            return CopilotState(**{**state.model_dump(),
                "aborted": True,
                "abort_reason": "Question contains disallowed content."})

    return CopilotState(**{**state.model_dump(), "ticker": ticker, "question": question})


# ── abort guard ───────────────────────────────────────────────────────────────

def _is_aborted(state: CopilotState) -> str:
    return "aborted" if state.aborted else "continue"


def _passthrough(state: CopilotState) -> CopilotState:
    return state


# ── node: assemble_response ───────────────────────────────────────────────────

def assemble_response(state: CopilotState) -> CopilotState:
    """
    Final node: nothing to mutate — the state is complete.
    The API handler reads state fields directly to build CopilotResponse.
    """
    return state


# ── graph builder ─────────────────────────────────────────────────────────────

def _build_graph() -> Any:
    graph = StateGraph(dict)   # Use dict; we handle Pydantic ourselves

    graph.add_node("validate_input",      lambda s: validate_input(CopilotState(**s)).model_dump())
    graph.add_node("retrieve_evidence",   lambda s: retrieve_evidence(CopilotState(**s)).model_dump())
    graph.add_node("run_calculations",    lambda s: run_calculations(CopilotState(**s)).model_dump())
    graph.add_node("synthesise",          lambda s: synthesise(CopilotState(**s)).model_dump())
    graph.add_node("validate_citations",  lambda s: citation_validator_node(CopilotState(**s)).model_dump())
    graph.add_node("assemble_response",   lambda s: assemble_response(CopilotState(**s)).model_dump())
    graph.add_node("aborted",             lambda s: s)   # terminal — no-op

    graph.set_entry_point("validate_input")

    graph.add_conditional_edges(
        "validate_input",
        lambda s: "aborted" if s.get("aborted") else "retrieve_evidence",
        {"aborted": "aborted", "retrieve_evidence": "retrieve_evidence"},
    )
    graph.add_edge("retrieve_evidence", "run_calculations")
    graph.add_edge("run_calculations",  "synthesise")
    graph.add_edge("synthesise",        "validate_citations")
    graph.add_edge("validate_citations","assemble_response")
    graph.add_edge("assemble_response", END)
    graph.add_edge("aborted",           END)

    return graph.compile()


_COPILOT_GRAPH = None


def _get_graph():
    global _COPILOT_GRAPH
    if _COPILOT_GRAPH is None:
        _COPILOT_GRAPH = _build_graph()
    return _COPILOT_GRAPH


# ── public entry point ────────────────────────────────────────────────────────

def run_copilot(
    question: str,
    ticker: str,
    market: str,
    session_id: str | None = None,
) -> CopilotResponse:
    """
    Run the full copilot pipeline and return a CopilotResponse.
    Raises no exceptions — errors are encoded in the response.
    """
    t0 = time.perf_counter()
    sid = session_id or str(uuid.uuid4())

    initial: Dict = CopilotState(
        session_id=sid,
        question=question,
        ticker=ticker,
        market=market,
    ).model_dump()

    try:
        graph  = _get_graph()
        result = graph.invoke(initial)
    except Exception as e:
        return CopilotResponse(
            session_id=sid,
            question=question,
            ticker=ticker,
            market=market,
            answer=f"An error occurred during research: {str(e)[:200]}",
            limitations=["Pipeline error — partial data may be missing."],
            citation_validation_passed=False,
            citation_issues=[str(e)[:200]],
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )

    state = CopilotState(**result)

    if state.aborted:
        return CopilotResponse(
            session_id=sid,
            question=question,
            ticker=ticker,
            market=market,
            answer=f"Request rejected: {state.abort_reason}",
            citation_validation_passed=False,
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )

    # Re-hydrate claims
    claims = [Claim(**c) if isinstance(c, dict) else c for c in (state.raw_claims or [])]

    return CopilotResponse(
        session_id=sid,
        question=question,
        ticker=ticker,
        market=market,
        answer=state.raw_answer or "No answer generated.",
        key_findings=state.raw_key_findings or [],
        claims=claims,
        sources=state.sources or [],
        calculations=[c for c in (state.calculations or []) if c.available],
        limitations=state.raw_limitations or [],
        unresolved=state.raw_unresolved or [],
        conflicting_evidence=state.raw_conflicting or [],
        data_warnings=state.raw_data_warnings or [],
        citation_validation_passed=state.citation_validation_passed,
        citation_issues=state.citation_issues or [],
        latency_ms=int((time.perf_counter() - t0) * 1000),
    )
