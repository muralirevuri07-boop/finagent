"""
Deterministic valuation engine for FinAgent Global.
Produces bear / base / bull DCF scenarios from real financial data.
The LLM never touches these numbers.
"""

from typing import Optional


# ── helpers ─────────────────────────────────────────────────────────────────

def _dcf(fcf_base: float, growth_rates: list[float], wacc: float,
         terminal_growth: float, years: int = 5) -> float:
    """
    Classic 2-stage DCF.
    Stage 1: explicit forecast (years 1-N at growth_rates[i]).
    Stage 2: Gordon-growth terminal value.
    Returns intrinsic equity value per share = (PV of FCFs + terminal - net debt) / shares.
    """
    if fcf_base <= 0:
        return 0.0

    pv = 0.0
    fcf = fcf_base
    for i in range(years):
        g    = growth_rates[i] if i < len(growth_rates) else growth_rates[-1]
        fcf  = fcf * (1 + g)
        pv  += fcf / (1 + wacc) ** (i + 1)

    # Terminal value (Gordon Growth)
    terminal_fcf = fcf * (1 + terminal_growth)
    tv           = terminal_fcf / (wacc - terminal_growth)
    pv          += tv / (1 + wacc) ** years

    return pv


def _growth_from_history(history: list[dict], key: str = "raw") -> Optional[float]:
    """Compute CAGR from last 2 available data points."""
    vals = [h[key] for h in history if h.get(key, 0) > 0]
    if len(vals) < 2:
        return None
    cagr = (vals[-1] / vals[0]) ** (1 / max(len(vals) - 1, 1)) - 1
    return round(min(max(cagr, -0.5), 1.0), 4)   # cap between -50% and +100%


# ── main entry ───────────────────────────────────────────────────────────────

def compute_valuation(financial_data: dict) -> dict:
    """
    Given the output of financial_agent, return a valuation dict:
    {
      "method":  str,
      "bear":    float | None,
      "base":    float | None,
      "bull":    float | None,
      "currency": str,
      "horizon":  str,
      "assumptions": dict,
      "upside_base": str,    # e.g. "+18.4%"
      "available": bool,
      "unavailable_reason": str | None,
    }
    """
    market   = financial_data.get("market", "US")
    currency = financial_data.get("currency", "$")
    ticker   = financial_data.get("ticker", "")
    non_equity = market in {"Crypto", "Forex", "Commodity"}

    # ── Non-equity: technical scenario only ──────────────────────────────────
    if non_equity:
        price = financial_data.get("current_price_raw", 0)
        if not price:
            return _unavailable("No price data for technical scenario.")
        hi_52 = _raw_price(financial_data.get("52w_high", ""))
        lo_52 = _raw_price(financial_data.get("52w_low",  ""))
        bear  = round(price * 0.80, 2)
        base  = round((price + hi_52) / 2, 2) if hi_52 else round(price * 1.10, 2)
        bull  = round(hi_52 * 1.05, 2)        if hi_52 else round(price * 1.25, 2)
        return {
            "method":    "Technical Range Scenario",
            "bear":      bear,
            "base":      base,
            "bull":      bull,
            "currency":  currency,
            "horizon":   "12 months",
            "assumptions": {
                "method_note": "52-week range used; no intrinsic value applicable.",
            },
            "upside_base": _upside(price, base),
            "available":   True,
            "unavailable_reason": None,
        }

    # ── Equity DCF ───────────────────────────────────────────────────────────
    fcf_history = financial_data.get("fcf_history", [])
    shares      = _to_float(financial_data.get("shares_outstanding", 0))
    cash        = financial_data.get("total_cash_raw", 0)
    debt        = financial_data.get("total_debt_raw", 0)
    price       = financial_data.get("current_price_raw", 0) or \
                  _raw_price(financial_data.get("current_price", ""))

    # Need at least 1 FCF data point and share count
    fcf_vals = [h["raw"] for h in fcf_history if h.get("raw", 0) != 0]
    if not fcf_vals or not shares or shares < 1:
        return _unavailable(
            "Insufficient FCF or share data for DCF. "
            f"FCF points: {len(fcf_vals)}, shares: {shares}."
        )

    fcf_base = fcf_vals[-1]   # most recent annual FCF
    if fcf_base <= 0:
        return _unavailable(
            f"Latest FCF is {fcf_base:,.0f} — negative/zero FCF makes DCF unreliable."
        )

    hist_growth = _growth_from_history(fcf_history, key="raw")
    # Clamp g_base FIRST, then derive bear/bull from the clamped value
    g_base = max(min(hist_growth if hist_growth is not None else 0.08, 0.30), 0.03)
    g_bear = max(g_base * 0.4,  0.01)
    g_bull = min(g_base * 1.6,  0.45)

    wacc           = _wacc_estimate(financial_data)
    terminal_growth = 0.025   # long-run 2.5%

    # Scenario growth arrays (years 1-5, then terminal)
    bear_rates = [g_bear] * 5
    base_rates = [g_base] * 3 + [g_base * 0.7] * 2
    bull_rates = [g_bull] * 3 + [g_bull * 0.6] * 2

    net_cash      = (cash - debt)           # can be negative (net debt)
    net_cash_ps   = net_cash / shares       # per share

    pv_bear = _dcf(fcf_base, bear_rates, wacc, terminal_growth)
    pv_base = _dcf(fcf_base, base_rates, wacc, terminal_growth)
    pv_bull = _dcf(fcf_base, bull_rates, wacc, terminal_growth)

    iv_bear = max(round((pv_bear / shares + net_cash_ps), 2), 0)
    iv_base = max(round((pv_base / shares + net_cash_ps), 2), 0)
    iv_bull = max(round((pv_bull / shares + net_cash_ps), 2), 0)

    return {
        "method":   "Discounted Cash Flow (2-stage)",
        "bear":     iv_bear,
        "base":     iv_base,
        "bull":     iv_bull,
        "currency": currency,
        "horizon":  "5 years",
        "assumptions": {
            "fcf_base_year":    fcf_history[-1].get("year") if fcf_history else "N/A",
            "fcf_base_value":   f"{currency}{fcf_base/1e9:.2f}B" if abs(fcf_base) >= 1e9
                                else f"{currency}{fcf_base/1e6:.2f}M",
            "growth_bear":      f"{round(g_bear*100,1)}% p.a.",
            "growth_base":      f"{round(g_base*100,1)}% p.a. (tapering yr 4-5)",
            "growth_bull":      f"{round(g_bull*100,1)}% p.a. (tapering yr 4-5)",
            "wacc":             f"{round(wacc*100,1)}%",
            "terminal_growth":  f"{round(terminal_growth*100,1)}%",
            "net_cash_per_share": f"{currency}{round(net_cash_ps,2)}",
            "shares_outstanding": f"{shares/1e9:.3f}B" if shares >= 1e9
                                  else f"{shares/1e6:.1f}M",
            "historical_fcf_cagr": f"{round((hist_growth or 0)*100,1)}%",
        },
        "upside_base": _upside(price, iv_base),
        "available":   True,
        "unavailable_reason": None,
    }


# ── private helpers ──────────────────────────────────────────────────────────

def _unavailable(reason: str) -> dict:
    return {
        "method":    "N/A",
        "bear":      None,
        "base":      None,
        "bull":      None,
        "currency":  "$",
        "horizon":   "N/A",
        "assumptions": {},
        "upside_base": "N/A",
        "available":   False,
        "unavailable_reason": reason,
    }


def _to_float(v) -> float:
    try:
        return float(v)
    except Exception:
        return 0.0


def _raw_price(price_str) -> float:
    """Strip currency symbol and parse float."""
    try:
        return float(str(price_str).replace("$","").replace("£","")
                                    .replace("₹","").replace("€","")
                                    .replace("¥","").replace(",",""))
    except Exception:
        return 0.0


def _upside(current: float, target: float) -> str:
    try:
        pct = (target - current) / current * 100
        sign = "+" if pct >= 0 else ""
        return f"{sign}{round(pct,1)}%"
    except Exception:
        return "N/A"


def _wacc_estimate(fin: dict) -> float:
    """
    Simple WACC proxy.
    Equity cost = risk-free (4%) + beta * equity premium (5.5%)
    Debt cost   = 5% pre-tax, assume 21% tax
    Weights from market cap vs debt where available.
    Falls back to 10% if data insufficient.
    """
    try:
        beta   = _to_float(fin.get("beta", 1.0)) or 1.0
        beta   = max(min(beta, 3.0), 0.3)
        ke     = 0.04 + beta * 0.055

        mkt_cap = _raw_cap(fin.get("market_cap", ""))
        debt    = fin.get("total_debt_raw", 0) or 0
        total   = mkt_cap + debt
        if total > 0:
            we   = mkt_cap / total
            wd   = debt    / total
            kd   = 0.05 * (1 - 0.21)
            wacc = we * ke + wd * kd
        else:
            wacc = ke

        return round(max(min(wacc, 0.20), 0.06), 4)   # clamp 6%–20%
    except Exception:
        return 0.10


def _raw_cap(cap_str: str) -> float:
    """Parse formatted market cap string back to float."""
    try:
        s = str(cap_str).strip()
        if s.endswith("T"):
            return float(s[:-1]) * 1e12
        if s.endswith("B"):
            return float(s[:-1]) * 1e9
        if s.endswith("M"):
            return float(s[:-1]) * 1e6
        return float(s.replace(",",""))
    except Exception:
        return 0.0
