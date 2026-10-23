"""
signal_scorer.py — Weighted quantitative signal score (0–100)

Components
──────────
  Sentiment    40 pts   Bullish → high, Bearish → low, Neutral → mid
  Valuation    40 pts   DCF upside to base vs current price
  Momentum     20 pts   Price vs 52-week range position

Final score → signal label + colour tier
  80–100  STRONG BUY   🟢
  60–79   BUY          🟢
  50–59   HOLD         🟡
  35–49   SELL         🔴
   0–34   STRONG SELL  🔴
"""

from __future__ import annotations


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
        breakdown      dict  {sentiment, valuation, momentum} component scores
        explanation    str   one-line human-readable summary
    """

    # ── SENTIMENT  (0–40) ────────────────────────────────────────────────────
    sent_label = sentiment.get("sentiment", "Neutral")
    sent_score = float(sentiment.get("score", 0.5))

    # score in [0,1] where 1 = Bullish, 0 = Bearish
    if sent_label == "Bullish":
        s_raw = 0.5 + (sent_score - 0.5)        # 0.5..1.0
    elif sent_label == "Bearish":
        s_raw = 0.5 - (sent_score - 0.5)        # 0.5..0.0  (inverted)
    else:
        s_raw = 0.5

    s_raw = max(0.0, min(1.0, s_raw))
    sentiment_pts = round(s_raw * 40)

    # ── VALUATION  (0–40) ────────────────────────────────────────────────────
    val_pts = 20  # neutral default when unavailable
    if valuation.get("available"):
        upside_str = valuation.get("upside_base", "0%")
        try:
            upside_pct = float(str(upside_str).replace("%", "").replace("+", "").strip())
        except (ValueError, TypeError):
            upside_pct = 0.0

        # Clamp: -50% → 0 pts, 0% → 20 pts, +30% → 40 pts, >+50% → capped 40
        if upside_pct >= 30:
            val_pts = 40
        elif upside_pct >= 0:
            val_pts = round(20 + (upside_pct / 30) * 20)
        elif upside_pct >= -30:
            val_pts = round(20 + (upside_pct / 30) * 20)   # goes below 20
        else:
            val_pts = 0
        val_pts = max(0, min(40, val_pts))

    # ── MOMENTUM  (0–20) ─────────────────────────────────────────────────────
    # Where is current price in the 52-week range?
    momentum_pts = 10  # neutral default
    try:
        raw_high = financial_data.get("52w_high", "")
        raw_low  = financial_data.get("52w_low",  "")
        raw_cur  = financial_data.get("current_price", "")

        def _strip(v: object) -> float:
            return float(str(v).replace(",", "").replace("$", "").replace("£", "")
                         .replace("₹", "").replace("€", "").replace("¥", "")
                         .replace("HK$", "").replace("S$", "").strip())

        high = _strip(raw_high)
        low  = _strip(raw_low)
        cur  = _strip(raw_cur)

        if high > low and cur >= low:
            position = (cur - low) / (high - low)   # 0 = at 52w low, 1 = at 52w high
            # Mid-range (0.4–0.6) neutral; near high bullish; near low bearish
            if position >= 0.7:
                momentum_pts = 16
            elif position >= 0.5:
                momentum_pts = 13
            elif position >= 0.3:
                momentum_pts = 10
            elif position >= 0.15:
                momentum_pts = 6
            else:
                momentum_pts = 3
    except (ValueError, TypeError, AttributeError):
        pass

    # ── TOTAL ────────────────────────────────────────────────────────────────
    total = sentiment_pts + val_pts + momentum_pts
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
        f"Sentiment {sentiment_pts}/40, "
        f"Valuation {val_pts}/40, "
        f"Momentum {momentum_pts}/20"
    )

    return {
        "score":       total,
        "label":       label,
        "tier":        tier,
        "breakdown": {
            "sentiment": sentiment_pts,
            "valuation": val_pts,
            "momentum":  momentum_pts,
        },
        "explanation": explanation,
    }
