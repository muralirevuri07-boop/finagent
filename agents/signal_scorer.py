"""
signal_scorer.py — Weighted quantitative signal score (0–100)

Components
──────────
  Sentiment    30 pts   Bullish → high, Bearish → low, Neutral → mid
  Valuation    40 pts   DCF upside (preferred) OR P/E-based fallback
  Momentum     30 pts   Price vs 52-week range + day change

Final score → signal label + colour tier
  80–100  STRONG BUY   🟢
  60–79   BUY          🟢
  50–59   HOLD         🟡
  35–49   SELL         🔴
   0–34   STRONG SELL  🔴

Fix (2026-10-23): removed the bias caused by the 20-pt valuation default when
DCF is unavailable.  When DCF fails we now use a P/E fallback.  When even that
is unavailable the valuation component is excluded and the score is rescaled
to 100 from the remaining two components. Sentiment weight also reduced from 40
to 30 so a bullish LLM summary alone cannot push a stock into BUY territory.
Momentum boosted to 30 so hard price data has more influence.
"""

from __future__ import annotations
import math


def _strip(v: object) -> float:
    """Strip currency symbols, commas, spaces → float. Raises ValueError on failure."""
    s = (str(v)
         .replace(",", "")
         .replace("$", "").replace("£", "").replace("₹", "")
         .replace("€", "").replace("¥", "").replace("p", "")
         .replace("HK", "").replace("S", "")   # after currency-prefix strips
         .strip())
    return float(s)


def _parse_pct(v: object) -> float:
    """Strip % signs and return float percentage (e.g. '+12.5%' → 12.5)."""
    return float(str(v).replace("%", "").replace("+", "").strip())


def _val_from_pe(financial_data: dict) -> tuple[int, str]:
    """
    Valuation pts (0–40) derived from P/E when DCF is unavailable.

    Heuristic (industry-agnostic):
      P/E < 10         → 36–40 pts  (cheap)
      P/E 10–20        → 28–35 pts  (fair)
      P/E 20–30        → 20–27 pts  (moderate)
      P/E 30–50        → 10–19 pts  (expensive)
      P/E > 50         →  0–9 pts   (very expensive)
      P/E negative / N/A → None     (exclude)

    Also considers forward P/E when available (lower fwd P/E = earnings growth).
    Returns (pts | None, method_note).
    """
    def _pe(key: str) -> float | None:
        raw = financial_data.get(key, "N/A")
        if raw in ("N/A", None, "", "—"):
            return None
        try:
            v = _strip(raw)
            return v if v > 0 else None
        except (ValueError, TypeError):
            return None

    pe  = _pe("pe_ratio") or _pe("pe_ttm") or _pe("P/E (TTM)")
    fpe = _pe("fwd_pe")   or _pe("fwd_pe_ratio") or _pe("forward_pe")

    if pe is None and fpe is None:
        return -1, "no_pe"   # -1 signals: exclude valuation component

    # Use forward P/E if it implies earnings growth (fpe < pe), else trailing P/E
    ratio = pe
    note = "trailing P/E"
    if fpe is not None:
        if pe is None or fpe < pe:
            ratio = fpe
            note = "forward P/E"

    assert ratio is not None
    if ratio < 10:
        pts = 38
    elif ratio < 15:
        pts = 33
    elif ratio < 20:
        pts = 28
    elif ratio < 25:
        pts = 22
    elif ratio < 30:
        pts = 17
    elif ratio < 40:
        pts = 12
    elif ratio < 60:
        pts = 6
    else:
        pts = 2

    return pts, f"P/E fallback ({note}={ratio:.1f}x)"


def compute_signal_score(
    sentiment: dict,
    valuation: dict,
    financial_data: dict,
) -> dict:
    """
    Returns:
        score          0–100 int
        label          str   e.g. "STRONG BUY"
        tier           str   "strong_buy" | "buy" | "hold" | "sell" | "strong_sell"
        breakdown      dict  {sentiment, valuation, momentum}
        explanation    str   one-line human-readable summary
        valuation_method str how valuation pts were derived
    """

    # ── SENTIMENT  (0–30) ────────────────────────────────────────────────────
    sent_label = sentiment.get("sentiment", "Neutral")
    sent_score = float(sentiment.get("score", 0.5))

    if sent_label == "Bullish":
        s_raw = 0.5 + (sent_score - 0.5)      # maps to 0.5–1.0
    elif sent_label == "Bearish":
        s_raw = 0.5 - (sent_score - 0.5)      # maps to 0.5–0.0
    else:
        s_raw = 0.5

    s_raw = max(0.0, min(1.0, s_raw))
    sentiment_pts = round(s_raw * 30)           # max 30

    # ── VALUATION  (0–40) ────────────────────────────────────────────────────
    val_pts: int | None = None
    val_method = "unavailable"

    if valuation.get("available"):
        # DCF preferred
        try:
            upside_pct = _parse_pct(valuation.get("upside_base", "0%"))
            if upside_pct >= 30:
                val_pts = 40
            elif upside_pct >= 0:
                val_pts = round(20 + (upside_pct / 30) * 20)
            elif upside_pct >= -30:
                val_pts = round(20 + (upside_pct / 30) * 20)
            else:
                val_pts = 0
            val_pts = max(0, min(40, val_pts))
            val_method = f"DCF upside {upside_pct:+.1f}%"
        except (ValueError, TypeError):
            pass

    if val_pts is None:
        # P/E fallback
        pe_pts, pe_method = _val_from_pe(financial_data)
        if pe_pts >= 0:
            val_pts = pe_pts
            val_method = pe_method
        # else: val_pts stays None → exclude from score, rescale

    # ── MOMENTUM  (0–30) ─────────────────────────────────────────────────────
    momentum_pts = 15  # neutral default (only used if parse fails)
    momentum_computed = False
    try:
        raw_high = financial_data.get("52w_high", "")
        raw_low  = financial_data.get("52w_low",  "")
        raw_cur  = financial_data.get("current_price", "")

        high = _strip(raw_high)
        low  = _strip(raw_low)
        cur  = _strip(raw_cur)

        if high > low and cur >= low:
            position = (cur - low) / (high - low)   # 0=52w low, 1=52w high
            if position >= 0.80:
                range_pts = 24   # near 52w high → bearish mean-reversion risk
            elif position >= 0.60:
                range_pts = 20
            elif position >= 0.40:
                range_pts = 15
            elif position >= 0.20:
                range_pts = 8
            else:
                range_pts = 3   # near 52w low

            # Day change bonus/penalty (−3 to +6)
            day_change_pts = 0
            try:
                day_str = (financial_data.get("day_change_pct", "")
                           or financial_data.get("change_pct", "")
                           or "0%")
                day_chg = _parse_pct(day_str)
                if day_chg >= 2:
                    day_change_pts = 6
                elif day_chg >= 0.5:
                    day_change_pts = 3
                elif day_chg <= -3:
                    day_change_pts = -3
                elif day_chg <= -1:
                    day_change_pts = -1
            except (ValueError, TypeError):
                pass

            momentum_pts = max(0, min(30, range_pts + day_change_pts))
            momentum_computed = True
    except (ValueError, TypeError, AttributeError):
        pass

    # ── TOTAL — rescale if valuation excluded ────────────────────────────────
    val_available = val_pts is not None
    if val_available:
        assert val_pts is not None
        raw_total = sentiment_pts + val_pts + momentum_pts
        max_possible = 100
        val_display = val_pts
    else:
        # Only sentiment (30) + momentum (30) = 60 max → rescale to 100
        raw_total = sentiment_pts + momentum_pts
        max_possible = 60
        val_display = 0

    # Rescale to 0–100
    total = round(raw_total / max_possible * 100) if max_possible > 0 else 50
    total = max(0, min(100, total))

    if total >= 80:
        label, tier = "STRONG BUY",  "strong_buy"
    elif total >= 60:
        label, tier = "BUY",         "buy"
    elif total >= 50:
        label, tier = "HOLD",        "hold"
    elif total >= 35:
        label, tier = "SELL",        "sell"
    else:
        label, tier = "STRONG SELL", "strong_sell"

    explanation = (
        f"Signal score {total}/100 — "
        f"Sentiment {sentiment_pts}/30, "
        f"Valuation {val_display}/40 [{val_method}], "
        f"Momentum {momentum_pts}/30"
        + ("" if val_available else " [valuation excluded — rescaled]")
    )

    return {
        "score":            total,
        "label":            label,
        "tier":             tier,
        "breakdown": {
            "sentiment": sentiment_pts,
            "valuation": val_display,
            "momentum":  momentum_pts,
        },
        "valuation_method": val_method,
        "explanation":      explanation,
    }
