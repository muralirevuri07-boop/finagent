"""
Scenario shock calculator — deterministic, no LLM.

V_i_scenario = V_i × (1 + s_i)
where s_i is the fractional price shock supplied by the user (e.g. -0.20 for -20 %).

Shocks are applied only to holdings that have a base value.
Holdings without a base value are listed but not shocked.
No correlation or second-order effects are modelled.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .models import (
    PortfolioValuation, ScenarioHoldingResult, ScenarioResult,
)


def build_scenario(
    valuation: PortfolioValuation,
    shocks: Dict[str, float],
    label: str = "User-defined shock",
) -> ScenarioResult:
    """
    Apply user-supplied price shocks to the current valuation.

    Parameters
    ----------
    valuation : PortfolioValuation
        Current portfolio valuation (output of build_portfolio_valuation).
    shocks : dict
        {symbol: fractional_shock}  e.g. {"AAPL": -0.20, "MSFT": 0.10}
        Keys are matched case-insensitively against holding symbols.
    label : str
        Human-readable scenario name.

    Returns
    -------
    ScenarioResult
    """
    # Normalise shock keys to upper-case for lookup
    shock_map = {k.upper(): float(v) for k, v in shocks.items()}

    base_total = valuation.total_value  # may be None
    scenario_total: float = 0.0
    results: List[ScenarioHoldingResult] = []

    for hv in valuation.holdings:
        sym_upper = hv.symbol.upper()
        shock_pct = shock_map.get(sym_upper)  # fraction, e.g. -0.20
        base_val  = hv.value_base             # None when price/FX unavailable

        if base_val is None:
            # Cannot shock — include for completeness
            results.append(ScenarioHoldingResult(
                symbol=hv.symbol,
                base_value=None,
                shock_pct=round(shock_pct * 100, 4) if shock_pct is not None else None,
                scenario_value=None,
                change=None,
            ))
            # Still accumulate unshocked value if no shock specified
            continue

        if shock_pct is not None:
            scenario_val = base_val * (1.0 + shock_pct)
            change = scenario_val - base_val
        else:
            # No shock specified for this symbol — value unchanged
            scenario_val = base_val
            change = 0.0

        scenario_total += scenario_val

        results.append(ScenarioHoldingResult(
            symbol=hv.symbol,
            base_value=round(base_val, 4),
            shock_pct=round(shock_pct * 100, 4) if shock_pct is not None else None,
            scenario_value=round(scenario_val, 4),
            change=round(change, 4),
        ))

    # Also add unvalued holdings that have no base_val but had a shock key
    # (already added above — loop already covers all holdings)

    total_change: Optional[float] = None
    total_change_pct: Optional[float] = None
    if base_total is not None and base_total > 0:
        total_change = round(scenario_total - base_total, 4)
        total_change_pct = round(total_change / base_total * 100, 4)

    return ScenarioResult(
        label=label,
        assumptions=shocks,
        base_portfolio_value=round(base_total, 4) if base_total is not None else None,
        scenario_portfolio_value=round(scenario_total, 4) if scenario_total > 0 else None,
        total_change=total_change,
        total_change_pct=total_change_pct,
        holdings=results,
    )
