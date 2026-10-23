"""
Portfolio Intelligence & Risk Engine — Pydantic models.

All financial numbers traceable to validated inputs or marked unavailable.
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field, field_validator
import math


# ── Enums ─────────────────────────────────────────────────────────────────────

class InstrumentType(str, Enum):
    EQUITY    = "equity"
    ETF       = "etf"
    CRYPTO    = "crypto"
    UNKNOWN   = "unknown"

class Market(str, Enum):
    US        = "US"
    NSE       = "NSE"
    BSE       = "BSE"
    LSE       = "LSE"
    FRANKFURT = "Frankfurt"
    TOKYO     = "Tokyo"
    HONGKONG  = "HongKong"
    SINGAPORE = "Singapore"
    CRYPTO    = "Crypto"

class DataStatus(str, Enum):
    OK          = "ok"
    STALE       = "stale"
    UNAVAILABLE = "unavailable"
    PARTIAL     = "partial"

class ValuationStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL  = "partial"
    EMPTY    = "empty"


# ── Input models ──────────────────────────────────────────────────────────────

class HoldingInput(BaseModel):
    """One holding as supplied by the client (localStorage)."""
    symbol: str
    market: str = "US"
    quantity: float
    purchase_price: Optional[float] = None   # cost basis, may be absent
    purchase_currency: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_finite_positive(cls, v: float) -> float:
        if not math.isfinite(v) or v <= 0:
            raise ValueError("quantity must be a finite positive number")
        return v

    @field_validator("purchase_price")
    @classmethod
    def purchase_price_must_be_finite(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (not math.isfinite(v) or v <= 0):
            raise ValueError("purchase_price must be finite and positive")
        return v

    model_config = ConfigDict(str_strip_whitespace=True)


class PortfolioAnalyseRequest(BaseModel):
    name: str = "My Portfolio"
    base_currency: str = "USD"
    holdings: List[HoldingInput]
    risk_free_rate: float = 0.045        # annualised, default 4.5 %
    history_days: int = Field(252, ge=30, le=1260)   # 1 trading year default
    scenario_shocks: Optional[Dict[str, float]] = None  # {symbol: -0.20}


# ── Market-data models ────────────────────────────────────────────────────────

class PricePoint(BaseModel):
    date: str
    close: float
    adjusted_close: Optional[float] = None
    currency: str


class HoldingMarketData(BaseModel):
    symbol: str
    yf_ticker: str
    name: str
    currency: str
    latest_price: Optional[float]
    price_timestamp: Optional[str]
    data_status: DataStatus
    unavailable_reason: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    asset_class: Optional[str] = None
    country: Optional[str] = None
    history: List[PricePoint] = []


# ── Valuation models ──────────────────────────────────────────────────────────

class HoldingValuation(BaseModel):
    symbol: str
    market: str
    quantity: float
    price: Optional[float]
    price_currency: str
    fx_rate: Optional[float]               # price_currency → base_currency
    value_base: Optional[float]            # None if price or FX missing
    allocation_pct: Optional[float]        # filled after portfolio total known
    cost_basis: Optional[float]            # quantity × purchase_price in base CCY
    unrealised_pnl: Optional[float]        # None if cost_basis unavailable
    unrealised_pnl_pct: Optional[float]
    data_status: DataStatus
    unavailable_reason: Optional[str] = None
    price_timestamp: Optional[str] = None
    sector: Optional[str] = None
    asset_class: Optional[str] = None


class PortfolioValuation(BaseModel):
    base_currency: str
    holdings: List[HoldingValuation]
    total_value: Optional[float]           # None if no holding is valued
    valued_count: int
    unvalued_count: int
    coverage_pct: float                    # valued / total holdings
    valuation_status: ValuationStatus
    partial_reason: Optional[str] = None
    retrieved_at: str


# ── Allocation models ─────────────────────────────────────────────────────────

class ConcentrationMetrics(BaseModel):
    hhi: Optional[float]                   # Herfindahl-Hirschman Index (fractions²)
    hhi_note: str
    top1_symbol: Optional[str]
    top1_pct: Optional[float]
    top5_pct: Optional[float]
    top10_pct: Optional[float]
    sector_breakdown: Dict[str, float]     # sector → pct; "Unclassified" if unknown
    asset_class_breakdown: Dict[str, float]
    currency_breakdown: Dict[str, float]


# ── Risk models ───────────────────────────────────────────────────────────────

class MetricResult(BaseModel):
    """Wrapper for any single risk metric — always carries availability status."""
    name: str
    value: Optional[float]
    units: str
    window_days: Optional[int]
    obs_count: Optional[int]
    obs_frequency: str                     # "daily", "weekly", etc.
    methodology: str
    available: bool
    unavailable_reason: Optional[str] = None


class DrawdownResult(BaseModel):
    max_drawdown_pct: Optional[float]
    peak_date: Optional[str]
    trough_date: Optional[str]
    recovery_date: Optional[str]           # None if not yet recovered
    window_days: Optional[int]
    available: bool
    unavailable_reason: Optional[str] = None


class CorrelationResult(BaseModel):
    symbols: List[str]
    matrix: Optional[List[List[Optional[float]]]]   # NxN, None for insufficient obs
    obs_count: Optional[int]
    window_days: Optional[int]
    methodology: str
    available: bool
    unavailable_reason: Optional[str] = None


class RiskMetrics(BaseModel):
    annualised_volatility: MetricResult
    max_drawdown: DrawdownResult
    sharpe_ratio: MetricResult
    var_95: MetricResult        # 1-day historical VaR at 95 %
    es_95: MetricResult         # Expected Shortfall at 95 %
    correlation: CorrelationResult
    obs_frequency: str
    history_days_used: int
    risk_free_rate_used: float
    methodology_note: str


# ── Scenario models ───────────────────────────────────────────────────────────

class ScenarioHoldingResult(BaseModel):
    symbol: str
    base_value: Optional[float]
    shock_pct: Optional[float]
    scenario_value: Optional[float]
    change: Optional[float]


class ScenarioResult(BaseModel):
    label: str
    assumptions: Dict[str, float]           # symbol → shock fraction
    base_portfolio_value: Optional[float]
    scenario_portfolio_value: Optional[float]
    total_change: Optional[float]
    total_change_pct: Optional[float]
    holdings: List[ScenarioHoldingResult]
    methodology_note: str = (
        "Simple price-shock model. Does not capture correlations, "
        "liquidity, derivatives, non-linear exposures, or taxes."
    )
    is_hypothetical: bool = True


# ── Full response ─────────────────────────────────────────────────────────────

class PortfolioAnalysisResponse(BaseModel):
    portfolio_name: str
    base_currency: str
    valuation: PortfolioValuation
    concentration: ConcentrationMetrics
    risk: RiskMetrics
    scenario: Optional[ScenarioResult]
    ai_narrative: Optional[str]
    data_warnings: List[str]
    analysed_at: str
    methodology_version: str = "1.0"
