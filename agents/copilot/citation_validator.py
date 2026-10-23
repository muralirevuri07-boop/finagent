"""
citation_validator.py — Validates LLM-cited source IDs against the evidence set.

Every source ID the LLM references in its claims must exist in state.sources.
Fabricated IDs are removed from the claim's source_ids list and flagged.
If any fabricated IDs are found, citation_validation_passed is set to False.
"""

from __future__ import annotations
from typing import List, Set

from agents.copilot.evidence_model import Claim, CopilotState


def validate_citations(state: CopilotState) -> CopilotState:
    """LangGraph node: strip fabricated source IDs and flag issues."""
    valid_ids: Set[str] = {s.id for s in (state.sources or [])}
    raw_claims: List[dict] = state.raw_claims or []
    issues: List[str] = []
    clean_claims: List[Claim] = []

    for raw in raw_claims:
        cited_ids: List[str] = raw.get("source_ids") or []
        valid_cited   = [sid for sid in cited_ids if sid in valid_ids]
        invalid_cited = [sid for sid in cited_ids if sid not in valid_ids]

        if invalid_cited:
            issues.append(
                f"Claim «{raw.get('text', '')[:80]}» cited unknown source IDs: {invalid_cited}"
            )

        claim = Claim(
            text=raw.get("text", ""),
            claim_type=raw.get("claim_type", "unknown"),
            source_ids=valid_cited,
            verified=len(valid_cited) > 0,
            limitation=raw.get("limitation"),
        )
        clean_claims.append(claim)

    validation_passed = len(issues) == 0

    return CopilotState(**{
        **state.model_dump(),
        "raw_claims": raw_claims,           # preserve originals
        "citation_validation_passed": validation_passed,
        "citation_issues": issues,
    }), clean_claims


# Wrapper that returns just the state (for LangGraph node interface)
def citation_validator_node(state: CopilotState) -> CopilotState:
    updated_state, clean_claims = validate_citations(state)
    # Store clean claims back; they'll be used by the final assembly step
    return CopilotState(**{
        **updated_state.model_dump(),
        # We can't store typed Claim objects in raw_claims (it's List[dict])
        # so convert back to dict for now; final assembly re-hydrates
        "raw_claims": [c.model_dump() for c in clean_claims],
    })
