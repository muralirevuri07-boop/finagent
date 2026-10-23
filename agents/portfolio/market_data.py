"""
Portfolio market-data service.

Uses yfinance for prices + history. Reuses MARKET_CONFIG from financial_agent.
Currency conversion uses yfinance FX pairs (e.g. GBPUSD=X).

Limitations:
- yfinance is not a guaranteed real-time, exchange-certified service.
- Prices may be delayed.
- NSE/BSE availability varies.
- Crypto tickers must include -USD suffix on yfinance.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import yfinance as yf

from .models import DataStatus, HoldingInput, HoldingMarketData, PricePoint

log = logging.getLogger(__name__)

# Market → yfinance suffix mapping (matches financial_agent.py)
MARKET_SUFFIX: Dict[str, str] = {
    "US":        "",
    "NSE":       ".NS",
    "BSE":       ".BO",
    "LSE":       ".L",
    "Frankfurt": ".DE",
    "Tokyo":     ".T",
    "HongKong":  ".HK",
    "Singapore": ".SI",
    "Crypto":    "-USD",   # e.g. BTC-USD
    "Forex":     "=X",
    "Commodity": "",
}

# Default currencies for each market (used when yfinance doesn't say)
MARKET_CURRENCY: Dict[str, str] = {
    "US":        "USD",
    "NSE":       "INR",
    "BSE":       "INR",
    "LSE":       "GBp",   # pence — converted to GBP in FX
    "Frankfurt": "EUR",
    "Tokyo":     "JPY",
    "HongKong":  "HKD",
    "Singapore": "SGD",
    "Crypto":    "USD",
    "Forex":     "USD",
    "Commodity": "USD",
}

_NOW = datetime.now(timezone.utc).isoformat()


def _yf_ticker(symbol: str, market: str) -> str:
    suffix = MARKET_SUFFIX.get(market, "")
    if market == "Crypto" and not symbol.endswith("-USD"):
        return f"{symbol}-USD"
    return f"{symbol}{suffix}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_holding_data(holding: HoldingInput, history_days: int) -> HoldingMarketData:
    """Fetch latest price + history for one holding. Never raises."""
    yft = _yf_ticker(holding.symbol, holding.market)
    period = f"{history_days}d"

    try:
        tk = yf.Ticker(yft)
        hist = tk.history(period=period, auto_adjust=True)
        info = {}
        try:
            info = tk.info or {}
        except Exception:
            pass

        if hist.empty:
            return HoldingMarketData(
                symbol=holding.symbol, yf_ticker=yft,
                name=info.get("longName") or holding.symbol,
                currency=info.get("currency") or MARKET_CURRENCY.get(holding.market, "USD"),
                latest_price=None, price_timestamp=None,
                data_status=DataStatus.UNAVAILABLE,
                unavailable_reason=f"yfinance returned no price history for {yft}",
            )

        latest_row = hist.iloc[-1]
        latest_price = float(latest_row["Close"])
        price_ts = str(hist.index[-1].date())
        currency = info.get("currency") or MARKET_CURRENCY.get(holding.market, "USD")

        # Build price history
        price_history: List[PricePoint] = []
        for dt, row in hist.iterrows():
            c = row.get("Close")
            if c is None or (c != c):  # NaN
                continue
            price_history.append(PricePoint(
                date=str(dt.date()),
                close=float(c),
                currency=currency,
            ))

        # Staleness check — warn if last price > 3 days old
        days_old = (datetime.now(timezone.utc).date() - hist.index[-1].date()).days
        status = DataStatus.STALE if days_old > 3 else DataStatus.OK

        return HoldingMarketData(
            symbol=holding.symbol,
            yf_ticker=yft,
            name=info.get("longName") or info.get("shortName") or holding.symbol,
            currency=currency,
            latest_price=latest_price,
            price_timestamp=price_ts,
            data_status=status,
            sector=info.get("sector"),
            industry=info.get("industry"),
            asset_class=_classify_asset(holding.market, info),
            country=info.get("country"),
            history=price_history,
        )

    except Exception as e:
        log.warning(f"[portfolio] fetch failed for {yft}: {e}")
        return HoldingMarketData(
            symbol=holding.symbol, yf_ticker=yft,
            name=holding.symbol,
            currency=MARKET_CURRENCY.get(holding.market, "USD"),
            latest_price=None, price_timestamp=None,
            data_status=DataStatus.UNAVAILABLE,
            unavailable_reason=str(e),
        )


def _classify_asset(market: str, info: dict) -> str:
    if market == "Crypto":
        return "Crypto"
    qt = (info.get("quoteType") or "").upper()
    if qt == "ETF":
        return "ETF"
    if qt in ("EQUITY", "STOCK"):
        return "Equity"
    return "Unknown"


def fetch_fx_rate(from_ccy: str, to_ccy: str) -> Tuple[Optional[float], Optional[str]]:
    """
    Return (rate, error_reason). rate converts 1 unit of from_ccy → to_ccy.
    Returns (1.0, None) when currencies are identical.
    LSE prices are in GBp (pence): treats GBp→GBP as /100, then GBP→base.
    """
    if from_ccy == to_ccy:
        return 1.0, None
    # Pence → Pound
    if from_ccy == "GBp":
        gbp_rate, err = fetch_fx_rate("GBP", to_ccy)
        if gbp_rate is None:
            return None, err
        return gbp_rate / 100.0, None
    try:
        pair = f"{from_ccy}{to_ccy}=X"
        tk = yf.Ticker(pair)
        hist = tk.history(period="5d")
        if hist.empty:
            return None, f"No FX data for {from_ccy}/{to_ccy}"
        rate = float(hist["Close"].iloc[-1])
        return rate, None
    except Exception as e:
        return None, str(e)


def fetch_all_holdings(
    holdings: List[HoldingInput], history_days: int
) -> List[HoldingMarketData]:
    """Sequential fetch for all holdings (avoids hammering yfinance)."""
    results = []
    for h in holdings:
        results.append(fetch_holding_data(h, history_days))
    return results
