"""
Deterministic risk-calculation module — no LLM.

Metrics:
  - Annualised volatility (daily returns × √252)
  - Maximum drawdown (peak-to-trough from cumulative return series)
  - Sharpe ratio (annualised excess return / annualised vol)
  - Historical VaR 95% (1-day, left tail)
  - Expected Shortfall 95% (mean of losses beyond VaR threshold)
  - Pairwise correlation matrix (from aligned daily returns)

All series validated: finite prices, positive prices, minimum obs requirement.
Missing observations are NOT treated as zero returns.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .models import (
    CorrelationResult, DrawdownResult, HoldingMarketData,
    MetricResult, RiskMetrics, PortfolioValuation,
)

# Minimum observations for each metric
MIN_OBS_VOL       = 20     # ~1 calendar month of daily data
MIN_OBS_DRAWDOWN  = 5
MIN_OBS_SHARPE    = 30
MIN_OBS_VAR       = 30
MIN_OBS_CORR      = 30     # per symbol pair
TRADING_DAYS_YEAR = 252


def _returns_from_prices(prices: pd.Series) -> pd.Series:
    """Simple price returns r_t = P_t / P_{t-1} - 1. Drops first NaN."""
    return prices.pct_change().dropna()


def _price_series(md: HoldingMarketData) -> Optional[pd.Series]:
    """Convert HoldingMarketData.history → validated, indexed pd.Series."""
    if not md.history:
        return None
    dates = []
    closes = []
    for p in md.history:
        try:
            c = float(p.close)
            if not math.isfinite(c) or c <= 0:
                continue
            dates.append(pd.Timestamp(p.date))
            closes.append(c)
        except (TypeError, ValueError):
            continue
    if len(closes) < 2:
        return None
    s = pd.Series(closes, index=dates).sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s


def _portfolio_price_series(
    market_data: List[HoldingMarketData],
    weights: Dict[str, float],
) -> Optional[pd.Series]:
    """
    Constant-weight buy-and-hold portfolio daily return series.
    IMPORTANT: labelled as modelled; actual past weights not known.
    Returns are aligned on common dates only.
    """
    return_series: Dict[str, pd.Series] = {}
    for md in market_data:
        if md.symbol not in weights:
            continue
        ps = _price_series(md)
        if ps is None or len(ps) < 2:
            continue
        r = _returns_from_prices(ps)
        if len(r) >= MIN_OBS_VOL:
            return_series[md.symbol] = r

    if not return_series:
        return None

    df = pd.DataFrame(return_series).dropna()
    if df.empty or len(df) < MIN_OBS_VOL:
        return None

    # Weighted portfolio return (constant weights)
    port_ret = sum(df[sym] * w for sym, w in weights.items() if sym in df.columns)
    return port_ret


def calc_annualised_volatility(returns: pd.Series, window_days: int) -> MetricResult:
    n = len(returns)
    if n < MIN_OBS_VOL:
        return MetricResult(
            name="Annualised Volatility", value=None, units="%",
            window_days=window_days, obs_count=n, obs_frequency="daily",
            methodology=f"σ_annual = s × √{TRADING_DAYS_YEAR}",
            available=False,
            unavailable_reason=f"Insufficient observations: {n} < {MIN_OBS_VOL}",
        )
    vol = float(returns.std(ddof=1)) * math.sqrt(TRADING_DAYS_YEAR) * 100
    return MetricResult(
        name="Annualised Volatility", value=round(vol, 4), units="%",
        window_days=window_days, obs_count=n, obs_frequency="daily",
        methodology=f"Sample std dev of daily returns × √{TRADING_DAYS_YEAR}",
        available=True,
    )


def calc_max_drawdown(returns: pd.Series, window_days: int) -> DrawdownResult:
    n = len(returns)
    if n < MIN_OBS_DRAWDOWN:
        return DrawdownResult(
            max_drawdown_pct=None, peak_date=None, trough_date=None,
            recovery_date=None, window_days=window_days, available=False,
            unavailable_reason=f"Insufficient observations: {n} < {MIN_OBS_DRAWDOWN}",
        )
    cum = (1 + returns).cumprod()
    rolling_max = cum.cummax()
    drawdown = (cum - rolling_max) / rolling_max
    trough_idx = drawdown.idxmin()
    peak_idx   = rolling_max.loc[:trough_idx].idxmax()
    mdd        = float(drawdown.min()) * 100

    def _date_str(idx: object) -> str:
        try:
            return str(idx.date())  # type: ignore[union-attr]
        except AttributeError:
            return str(idx)

    # Recovery: first date after trough where cum returns to rolling_max at trough
    recovery_date = None
    trough_pos = returns.index.get_loc(trough_idx)
    peak_val   = float(rolling_max[trough_idx])
    after_trough = cum.iloc[trough_pos + 1:]
    recovered = after_trough[after_trough >= peak_val]
    if not recovered.empty:
        idx0 = recovered.index[0]
        try:
            recovery_date = str(idx0.date())
        except AttributeError:
            recovery_date = str(idx0)

    return DrawdownResult(
        max_drawdown_pct=round(mdd, 4),
        peak_date=_date_str(peak_idx),
        trough_date=_date_str(trough_idx),
        recovery_date=recovery_date,
        window_days=window_days,
        available=True,
    )


def calc_sharpe(returns: pd.Series, risk_free_rate: float, window_days: int) -> MetricResult:
    n = len(returns)
    if n < MIN_OBS_SHARPE:
        return MetricResult(
            name="Sharpe Ratio", value=None, units="dimensionless",
            window_days=window_days, obs_count=n, obs_frequency="daily",
            methodology="(Ann. return − Rf) / Ann. vol",
            available=False,
            unavailable_reason=f"Insufficient observations: {n} < {MIN_OBS_SHARPE}",
        )
    daily_rf = (1 + risk_free_rate) ** (1 / TRADING_DAYS_YEAR) - 1
    excess   = returns - daily_rf
    ann_ret  = float(excess.mean()) * TRADING_DAYS_YEAR
    ann_vol  = float(excess.std(ddof=1)) * math.sqrt(TRADING_DAYS_YEAR)
    sharpe   = ann_ret / ann_vol if ann_vol > 0 else None

    return MetricResult(
        name="Sharpe Ratio",
        value=round(sharpe, 4) if sharpe is not None else None,
        units="dimensionless",
        window_days=window_days, obs_count=n, obs_frequency="daily",
        methodology=f"(Annualised excess return) / (Annualised vol). Rf={risk_free_rate*100:.2f}% p.a.",
        available=sharpe is not None,
        unavailable_reason=None if sharpe is not None else "Zero volatility",
    )


def calc_var_es(returns: pd.Series, window_days: int, confidence: float = 0.95) -> Tuple[MetricResult, MetricResult]:
    """Historical VaR and Expected Shortfall at `confidence` level, 1-day horizon."""
    n = len(returns)
    if n < MIN_OBS_VAR:
        unavail = MetricResult(
            name="", value=None, units="%", window_days=window_days,
            obs_count=n, obs_frequency="daily",
            methodology=f"Historical simulation, {confidence*100:.0f}% confidence",
            available=False,
            unavailable_reason=f"Insufficient observations: {n} < {MIN_OBS_VAR}",
        )
        var_r = unavail.model_copy(update={"name": f"VaR {confidence*100:.0f}%"})
        es_r  = unavail.model_copy(update={"name": f"ES {confidence*100:.0f}%"})
        return var_r, es_r

    losses = -returns  # flip sign: positive loss = bad
    var_threshold = float(np.quantile(losses, confidence))
    tail = losses[losses > var_threshold]
    es   = float(tail.mean()) if len(tail) > 0 else var_threshold

    var_result = MetricResult(
        name=f"VaR {confidence*100:.0f}%", value=round(var_threshold * 100, 4), units="%",
        window_days=window_days, obs_count=n, obs_frequency="daily",
        methodology=(
            f"Historical {confidence*100:.0f}% VaR. {confidence*100:.0f}th-percentile of "
            f"daily losses over {n} observations. Not a maximum-loss guarantee."
        ),
        available=True,
    )
    es_result = MetricResult(
        name=f"ES {confidence*100:.0f}%", value=round(es * 100, 4), units="%",
        window_days=window_days, obs_count=n, obs_frequency="daily",
        methodology=f"Mean of losses beyond {confidence*100:.0f}% VaR threshold.",
        available=True,
    )
    return var_result, es_result


def calc_correlation(market_data: List[HoldingMarketData], window_days: int) -> CorrelationResult:
    """Pairwise correlation matrix from aligned daily returns."""
    series_map: Dict[str, pd.Series] = {}
    for md in market_data:
        ps = _price_series(md)
        if ps is None:
            continue
        r = _returns_from_prices(ps)
        if len(r) >= MIN_OBS_CORR:
            series_map[md.symbol] = r

    syms = sorted(series_map.keys())
    if len(syms) < 2:
        return CorrelationResult(
            symbols=syms, matrix=None, obs_count=None, window_days=window_days,
            methodology="Pearson correlation of daily returns on common dates",
            available=False,
            unavailable_reason="Fewer than 2 symbols with sufficient history",
        )

    df = pd.DataFrame({s: series_map[s] for s in syms}).dropna()
    obs = len(df)
    if obs < MIN_OBS_CORR:
        return CorrelationResult(
            symbols=syms, matrix=None, obs_count=obs, window_days=window_days,
            methodology="Pearson correlation of daily returns on common dates",
            available=False,
            unavailable_reason=f"Only {obs} common observations (need {MIN_OBS_CORR})",
        )

    corr_matrix = df.corr(method="pearson")
    matrix_list: List[List[Optional[float]]] = []
    for i in syms:
        row = []
        for j in syms:
            v = corr_matrix.loc[i, j]
            row.append(round(float(v), 4) if not math.isnan(v) else None)
        matrix_list.append(row)

    return CorrelationResult(
        symbols=syms, matrix=matrix_list, obs_count=obs, window_days=window_days,
        methodology=(
            f"Pearson correlation of aligned daily returns over {obs} common trading days. "
            "Correlations are historical and period-dependent."
        ),
        available=True,
    )


def build_risk_metrics(
    market_data: List[HoldingMarketData],
    valuation: PortfolioValuation,
    risk_free_rate: float,
    history_days: int,
) -> RiskMetrics:
    """
    Compute all risk metrics from validated price history.
    Portfolio-level metrics use a constant-weight hypothetical portfolio.
    """
    total = valuation.total_value or 0.0
    weights: Dict[str, float] = {}
    if total > 0:
        for hv in valuation.holdings:
            if hv.value_base is not None:
                weights[hv.symbol] = hv.value_base / total

    # Portfolio return series (constant-weight, hypothetical)
    port_ret = _portfolio_price_series(market_data, weights)

    # Per-symbol correlation
    corr = calc_correlation(market_data, history_days)

    if port_ret is None or len(port_ret) < MIN_OBS_VOL:
        unavail_reason = "Insufficient aligned price history for portfolio-level metrics."
        return RiskMetrics(
            annualised_volatility=MetricResult(
                name="Annualised Volatility", value=None, units="%",
                window_days=history_days, obs_count=None, obs_frequency="daily",
                methodology=f"σ × √{TRADING_DAYS_YEAR}", available=False,
                unavailable_reason=unavail_reason,
            ),
            max_drawdown=DrawdownResult(
                available=False, unavailable_reason=unavail_reason,
                max_drawdown_pct=None, peak_date=None, trough_date=None,
                recovery_date=None, window_days=history_days,
            ),
            sharpe_ratio=MetricResult(
                name="Sharpe Ratio", value=None, units="dimensionless",
                window_days=history_days, obs_count=None, obs_frequency="daily",
                methodology="(Ann. return − Rf) / Ann. vol", available=False,
                unavailable_reason=unavail_reason,
            ),
            var_95=MetricResult(
                name="VaR 95%", value=None, units="%",
                window_days=history_days, obs_count=None, obs_frequency="daily",
                methodology="Historical simulation, 95% confidence", available=False,
                unavailable_reason=unavail_reason,
            ),
            es_95=MetricResult(
                name="ES 95%", value=None, units="%",
                window_days=history_days, obs_count=None, obs_frequency="daily",
                methodology="Mean loss beyond 95% VaR", available=False,
                unavailable_reason=unavail_reason,
            ),
            correlation=corr,
            obs_frequency="daily",
            history_days_used=history_days,
            risk_free_rate_used=risk_free_rate,
            methodology_note=(
                "Portfolio metrics use a constant-weight hypothetical portfolio. "
                "Actual past account performance may differ. "
                "Historical risk metrics do not predict future risk."
            ),
        )

    n = len(port_ret)
    vol   = calc_annualised_volatility(port_ret, history_days)
    mdd   = calc_max_drawdown(port_ret, history_days)
    sharpe = calc_sharpe(port_ret, risk_free_rate, history_days)
    var95, es95 = calc_var_es(port_ret, history_days)

    return RiskMetrics(
        annualised_volatility=vol,
        max_drawdown=mdd,
        sharpe_ratio=sharpe,
        var_95=var95,
        es_95=es95,
        correlation=corr,
        obs_frequency="daily",
        history_days_used=history_days,
        risk_free_rate_used=risk_free_rate,
        methodology_note=(
            f"Portfolio metrics use a constant-weight buy-and-hold model over {n} trading days. "
            "This is a modelled historical portfolio, not actual account performance. "
            "Historical risk metrics do not predict future risk."
        ),
    )
