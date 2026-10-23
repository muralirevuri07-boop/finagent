"""
FastAPI router for Portfolio Intelligence & Risk Engine.

POST /portfolio/analyse
  Body: PortfolioAnalyseRequest (JSON)
  Returns: PortfolioAnalysisResponse (JSON)

No auth required (matches existing finagent API design).
No DB — stateless per-request.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from .market_data import fetch_all_holdings
from .models import PortfolioAnalyseRequest, PortfolioAnalysisResponse
from .risk_engine import build_risk_metrics
from .scenario import build_scenario
from .valuation import build_concentration, build_portfolio_valuation

log = logging.getLogger(__name__)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.post("/analyse", response_model=PortfolioAnalysisResponse)
async def analyse_portfolio(req: PortfolioAnalyseRequest) -> PortfolioAnalysisResponse:
    """
    Full portfolio analysis: valuation → concentration → risk → scenario.

    All calculations are deterministic.
    AI narrative is omitted from this endpoint (see /portfolio/narrative).
    """
    if not req.holdings:
        raise HTTPException(status_code=422, detail="holdings list must not be empty")

    log.info(f"[portfolio] analyse request: {len(req.holdings)} holdings, base={req.base_currency}")

    # ── 1. Fetch market data ──────────────────────────────────────────────────
    market_data = fetch_all_holdings(req.holdings, req.history_days)

    # ── 2. Valuation ──────────────────────────────────────────────────────────
    valuation, warnings = build_portfolio_valuation(
        req.holdings, market_data, req.base_currency
    )

    # ── 3. Concentration ──────────────────────────────────────────────────────
    concentration = build_concentration(valuation)

    # ── 4. Risk metrics ───────────────────────────────────────────────────────
    risk = build_risk_metrics(
        market_data, valuation, req.risk_free_rate, req.history_days
    )

    # ── 5. Scenario (optional) ────────────────────────────────────────────────
    scenario = None
    if req.scenario_shocks:
        scenario = build_scenario(valuation, req.scenario_shocks)

    return PortfolioAnalysisResponse(
        portfolio_name=req.name,
        base_currency=req.base_currency,
        valuation=valuation,
        concentration=concentration,
        risk=risk,
        scenario=scenario,
        ai_narrative=None,   # Phase 5
        data_warnings=warnings,
        analysed_at=datetime.now(timezone.utc).isoformat(),
    )
