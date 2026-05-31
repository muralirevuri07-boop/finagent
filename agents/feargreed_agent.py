import requests

def feargreed_agent(state: dict) -> dict:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        
        # VIX for fear
        vix = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX?interval=1d&range=5d", headers=headers, timeout=10).json()
        vix_price = vix["chart"]["result"][0]["meta"]["regularMarketPrice"]
        
        # SP500 momentum
        sp500 = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?interval=1d&range=1mo", headers=headers, timeout=10).json()
        sp_closes = sp500["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        sp_closes = [x for x in sp_closes if x is not None]
        sp_momentum = ((sp_closes[-1] - sp_closes[0]) / sp_closes[0]) * 100

        # BTC momentum (crypto sentiment)
        btc = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/BTC-USD?interval=1d&range=5d", headers=headers, timeout=10).json()
        btc_closes = btc["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        btc_closes = [x for x in btc_closes if x is not None]
        btc_change = ((btc_closes[-1] - btc_closes[0]) / btc_closes[0]) * 100

        # Score calculation
        vix_score    = max(0, min(100, 100 - (vix_price - 10) * 2.5))
        momentum_score = max(0, min(100, 50 + sp_momentum * 3))
        btc_score    = max(0, min(100, 50 + btc_change * 2))
        final_score  = round((vix_score * 0.5 + momentum_score * 0.3 + btc_score * 0.2), 1)

        if final_score >= 75:   label = "Extreme Greed"
        elif final_score >= 55: label = "Greed"
        elif final_score >= 45: label = "Neutral"
        elif final_score >= 25: label = "Fear"
        else:                   label = "Extreme Fear"

        return {**state, "feargreed": {
            "score": final_score,
            "label": label,
            "vix": round(vix_price, 2),
            "sp500_momentum": round(sp_momentum, 2),
            "btc_change": round(btc_change, 2)
        }}
    except Exception as e:
        return {**state, "feargreed": {"score": 50, "label": "Neutral", "error": str(e)}}