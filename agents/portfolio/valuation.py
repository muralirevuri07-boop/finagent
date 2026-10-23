"""
Deterministic portfolio valuation.

V_i = q_i × P_i × FX_i
V_p = Σ V_i  (only valued holdings)

No LLM involved. All outputs traceable to validated inputs.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from .market_data import fetch_fx_rate
from .models import (
    ConcentrationMetrics, DataStatus, HoldingInput, HoldingMarketData,
    HoldingValuation, PortfolioValuation, ValuationStatus,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_pct(num: float, denom: float) -> Optional[float]:
    if denom and math.isfinite(denom) and denom != 0:
        return round(num / denom * 100, 4)
    return None


def build_portfolio_valuation(
    holdings_input: List[HoldingInput],
    market_data: List[HoldingMarketData],
    base_currency: str,
) -> Tuple[PortfolioValuation, List[str]]:
    """
    Returns (PortfolioValuation, data_warnings).
    Never fabricates prices or FX rates.
    """
    warnings: List[str] = []
    # Cache FX rates to avoid repeated lookups
    fx_cache: Dict[Tuple[str, str], Tuple[Optional[float], Optional[str]]] = {}

    def get_fx(from_ccy: str, to_ccy: str) -> Tuple[Optional[float], Optional[str]]:
        key = (from_ccy, to_ccy)
        if key not in fx_cache:
            fx_cache[key] = fetch_fx_rate(from_ccy, to_ccy)
        return fx_cache[key]

    valued_holdings: List[HoldingValuation] = []
    total_value: float = 0.0
    valued_count = 0
    unvalued_count = 0

    for inp, mkt in zip(holdings_input, market_data):
        price = mkt.latest_price
        price_ccy = mkt.currency

        # --- price unavailable ---
        if price is None or not math.isfinite(price):
            valued_holdings.append(HoldingValuation(
                symbol=inp.symbol, market=inp.market,
                quantity=inp.quantity,
                price=None, price_currency=price_ccy,
                fx_rate=None, value_base=None,
                allocation_pct=None,
                cost_basis=None, unrealised_pnl=None, unrealised_pnl_pct=None,
                data_status=DataStatus.UNAVAILABLE,
                unavailable_reason=mkt.unavailable_reason or "Price unavailable",
                price_timestamp=mkt.price_timestamp,
                sector=mkt.sector, asset_class=mkt.asset_class,
            ))
            unvalued_count += 1
            warnings.append(f"{inp.symbol}: price unavailable — excluded from portfolio value.")
            continue

        # --- FX conversion ---
        fx_rate, fx_err = get_fx(price_ccy, base_currency)
        if fx_rate is None:
            valued_holdings.append(HoldingValuation(
                symbol=inp.symbol, market=inp.market,
                quantity=inp.quantity,
                price=price, price_currency=price_ccy,
                fx_rate=None, value_base=None,
                allocation_pct=None,
                cost_basis=None, unrealised_pnl=None, unrealised_pnl_pct=None,
                data_status=DataStatus.UNAVAILABLE,
                unavailable_reason=f"FX conversion {price_ccy}→{base_currency} failed: {fx_err}",
                price_timestamp=mkt.price_timestamp,
                sector=mkt.sector, asset_class=mkt.asset_class,
            ))
            unvalued_count += 1
            warnings.append(f"{inp.symbol}: FX {price_ccy}→{base_currency} unavailable.")
            continue

        # --- valuation ---
        value_base = inp.quantity * price * fx_rate
        total_value += value_base
        valued_count += 1

        # cost basis (only when purchase_price supplied)
        cost_basis: Optional[float] = None
        unrealised_pnl: Optional[float] = None
        unrealised_pnl_pct: Optional[float] = None
        if inp.purchase_price is not None:
            pb_ccy = inp.purchase_currency or price_ccy
            pb_fx, _ = get_fx(pb_ccy, base_currency)
            if pb_fx is not None:
                cost_basis = inp.quantity * inp.purchase_price * pb_fx
                unrealised_pnl = value_base - cost_basis
                if cost_basis > 0:
                    unrealised_pnl_pct = round(unrealised_pnl / cost_basis * 100, 4)

        valued_holdings.append(HoldingValuation(
            symbol=inp.symbol, market=inp.market,
            quantity=inp.quantity,
            price=round(price, 6), price_currency=price_ccy,
            fx_rate=round(fx_rate, 6),
            value_base=round(value_base, 4),
            allocation_pct=None,   # filled below once total known
            cost_basis=round(cost_basis, 4) if cost_basis is not None else None,
            unrealised_pnl=round(unrealised_pnl, 4) if unrealised_pnl is not None else None,
            unrealised_pnl_pct=unrealised_pnl_pct,
            data_status=mkt.data_status,
            unavailable_reason=None,
            price_timestamp=mkt.price_timestamp,
            sector=mkt.sector, asset_class=mkt.asset_class,
        ))

    # --- fill allocation % ---
    n = len(holdings_input)
    if total_value > 0:
        for hv in valued_holdings:
            if hv.value_base is not None:
                hv.allocation_pct = _safe_pct(hv.value_base, total_value)

    if unvalued_count > 0:
        warnings.append(
            f"Partial valuation: {valued_count}/{n} holdings valued. "
            "Total represents only the valued portion."
        )

    if n == 0 or valued_count == 0:
        status = ValuationStatus.EMPTY
    elif unvalued_count > 0:
        status = ValuationStatus.PARTIAL
    else:
        status = ValuationStatus.COMPLETE

    coverage = round(valued_count / n * 100, 1) if n else 0.0

    return PortfolioValuation(
        base_currency=base_currency,
        holdings=valued_holdings,
        total_value=round(total_value, 4) if valued_count > 0 else None,
        valued_count=valued_count,
        unvalued_count=unvalued_count,
        coverage_pct=coverage,
        valuation_status=status,
        partial_reason="Some holdings could not be priced or converted." if unvalued_count else None,
        retrieved_at=_now_iso(),
    ), warnings


def build_concentration(valuation: PortfolioValuation) -> ConcentrationMetrics:
    """
    Allocation, HHI, top-N, sector/asset/currency breakdowns.
    All weights derived from validated value_base / total_value.
    Denominator = total valued portfolio value only.
    """
    total = valuation.total_value or 0.0
    valued = [h for h in valuation.holdings if h.value_base is not None and total > 0]

    if not valued:
        return ConcentrationMetrics(
            hhi=None, hhi_note="No valued holdings",
            top1_symbol=None, top1_pct=None, top5_pct=None, top10_pct=None,
            sector_breakdown={}, asset_class_breakdown={}, currency_breakdown={},
        )

    # Weights as fractions
    weights = [(h.symbol, h.value_base / total) for h in valued]
    weights.sort(key=lambda x: x[1], reverse=True)

    hhi = round(sum(w ** 2 for _, w in weights), 6)
    hhi_note = (
        "HHI computed from valued holdings only. "
        "Range: 0 (perfectly diversified) to 1 (single holding). "
        "No universal safe threshold."
    )

    top1 = weights[0] if weights else None
    top5_pct = round(sum(w for _, w in weights[:5]) * 100, 2)
    top10_pct = round(sum(w for _, w in weights[:10]) * 100, 2)

    # Sector breakdown
    sector_map: dict = {}
    asset_map: dict = {}
    ccy_map: dict = {}

    for h in valued:
        pct = h.value_base / total * 100
        sec = h.sector or "Unclassified"
        sector_map[sec] = round(sector_map.get(sec, 0) + pct, 4)
        ac = h.asset_class or "Unknown"
        asset_map[ac] = round(asset_map.get(ac, 0) + pct, 4)
        ccy = h.price_currency or "Unknown"
        ccy_map[ccy] = round(ccy_map.get(ccy, 0) + pct, 4)

    return ConcentrationMetrics(
        hhi=hhi,
        hhi_note=hhi_note,
        top1_symbol=top1[0] if top1 else None,
        top1_pct=round(top1[1] * 100, 2) if top1 else None,
        top5_pct=top5_pct,
        top10_pct=top10_pct,
        sector_breakdown=sector_map,
        asset_class_breakdown=asset_map,
        currency_breakdown=ccy_map,
    )
