import streamlit as st
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dotenv import load_dotenv
load_dotenv()

st.set_page_config(page_title="FinAgent Global", page_icon="⬡", layout="wide", initial_sidebar_state="collapsed")

def get_theme(rec="N/A"):
    themes = {
        "BUY":  {"p":"#00ff9d","s":"#00c8ff","g":"rgba(0,255,157,","a1":"#003320","a2":"#001a33","a3":"#002233"},
        "SELL": {"p":"#ff0066","s":"#ff6600","g":"rgba(255,0,102,","a1":"#330010","a2":"#1a0000","a3":"#2d0015"},
        "HOLD": {"p":"#ffaa00","s":"#ff6600","g":"rgba(255,170,0,","a1":"#332200","a2":"#1a1000","a3":"#2d1f00"},
        "N/A":  {"p":"#00ff9d","s":"#00c8ff","g":"rgba(0,255,157,","a1":"#003320","a2":"#001a33","a3":"#002233"},
    }
    return themes.get(rec, themes["N/A"])

def inject_css(t):
    p,s,g,a1,a2,a3 = t["p"],t["s"],t["g"],t["a1"],t["a2"],t["a3"]
    st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Share+Tech+Mono&display=swap');
*{{box-sizing:border-box;}}
.stApp{{background:#000510;overflow-x:hidden;}}
.stApp::before{{content:'';position:fixed;top:0;left:0;right:0;bottom:0;
background:radial-gradient(ellipse 120% 40% at 20% 0%,{a1} 0%,transparent 60%),
radial-gradient(ellipse 100% 50% at 80% 10%,{a2} 0%,transparent 55%),
radial-gradient(ellipse 80% 60% at 50% 5%,{a3} 0%,transparent 50%);
animation:aurora 12s ease-in-out infinite alternate;pointer-events:none;z-index:0;}}
@keyframes aurora{{0%{{opacity:0.6;transform:scale(1);}}50%{{opacity:0.9;transform:scale(1.05);}}100%{{opacity:1;transform:scale(1.02);}}}}
.stApp::after{{content:'';position:fixed;top:0;left:0;right:0;bottom:0;
background-image:linear-gradient({g}0.04) 1px,transparent 1px),linear-gradient(90deg,{g}0.04) 1px,transparent 1px);
background-size:60px 60px;pointer-events:none;z-index:0;}}
.ticker-wrap{{width:100%;overflow:hidden;background:rgba(0,0,0,0.7);border-bottom:1px solid {g}0.3);padding:6px 0;position:relative;z-index:10;margin-bottom:1rem;}}
.ticker{{display:flex;width:max-content;animation:ticker 30s linear infinite;}}
.ticker-item{{font-family:'Share Tech Mono',monospace;font-size:0.75rem;padding:0 2rem;white-space:nowrap;color:{p};}}
@keyframes ticker{{0%{{transform:translateX(0);}}100%{{transform:translateX(-50%);}}}}
.hero-title{{font-family:'Orbitron',monospace;font-size:2.8rem;font-weight:900;
background:linear-gradient(90deg,{p},{s},{p});background-size:300%;
-webkit-background-clip:text;-webkit-text-fill-color:transparent;
animation:gradientShift 4s ease infinite;text-align:center;
filter:drop-shadow(0 0 30px {g}0.6));position:relative;z-index:1;}}
@keyframes gradientShift{{0%{{background-position:0%;}}50%{{background-position:100%;}}100%{{background-position:0%;}}}}
.hero-sub{{font-family:'Share Tech Mono',monospace;color:{g}0.5);text-align:center;font-size:0.75rem;letter-spacing:4px;text-transform:uppercase;position:relative;z-index:1;margin-bottom:1rem;}}
.metric-card{{background:rgba(0,5,16,0.85);border:1px solid {g}0.3);border-radius:14px;padding:1.2rem 0.8rem;text-align:center;position:relative;overflow:hidden;backdrop-filter:blur(20px);animation:flyIn 0.6s ease forwards;z-index:1;}}
.metric-card::before{{content:'';position:absolute;top:0;left:-200%;width:60%;height:1px;background:linear-gradient(90deg,transparent,{p},transparent);animation:scanLine 3s ease-in-out infinite;}}
@keyframes scanLine{{0%{{left:-200%;}}100%{{left:200%;}}}}
@keyframes flyIn{{from{{opacity:0;transform:translateY(30px);}}to{{opacity:1;transform:translateY(0);}}}}
.metric-label{{font-family:'Share Tech Mono',monospace;color:{g}0.5);font-size:0.62rem;letter-spacing:2px;text-transform:uppercase;margin-bottom:0.5rem;}}
.metric-value{{font-family:'Orbitron',monospace;font-size:1.3rem;font-weight:700;color:{p};text-shadow:0 0 20px {g}0.8);}}
.rec-value{{font-family:'Orbitron',monospace;font-size:1.5rem;font-weight:900;color:{p};text-shadow:0 0 30px {g}1),0 0 60px {g}0.5);animation:recPulse 2s ease-in-out infinite;}}
@keyframes recPulse{{0%,100%{{text-shadow:0 0 20px {g}0.7);}}50%{{text-shadow:0 0 40px {g}1),0 0 80px {g}0.5);}}}}
.data-panel{{background:rgba(0,5,16,0.8);border:1px solid {g}0.2);border-radius:14px;padding:1.5rem;backdrop-filter:blur(20px);margin-bottom:1rem;position:relative;overflow:hidden;z-index:1;animation:flyIn 0.8s ease forwards;}}
.data-panel::before{{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,{p},{s},transparent);opacity:0.6;}}
.panel-title{{font-family:'Orbitron',monospace;color:{p};font-size:0.72rem;letter-spacing:3px;text-transform:uppercase;margin-bottom:1rem;padding-bottom:0.5rem;border-bottom:1px solid {g}0.15);}}
.data-row{{display:flex;justify-content:space-between;padding:0.4rem 0;border-bottom:1px solid rgba(255,255,255,0.04);font-family:'Share Tech Mono',monospace;font-size:0.82rem;}}
.data-key{{color:{g}0.45);}} .data-val{{color:#fff;font-weight:bold;}}
.reasoning-text{{font-family:'Share Tech Mono',monospace;color:rgba(255,255,255,0.82);font-size:0.82rem;line-height:2;border-left:2px solid {p};padding-left:1rem;}}
.risk-badge{{background:rgba(255,0,102,0.07);border:1px solid rgba(255,0,102,0.25);border-radius:8px;padding:0.5rem 0.8rem;font-family:'Share Tech Mono',monospace;color:#ff6699;font-size:0.78rem;margin:0.25rem 0;}}
.agent-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:0.5rem;margin:0.8rem 0;position:relative;z-index:1;}}
.agent-card{{background:{g}0.07);border:1px solid {g}0.25);border-radius:10px;padding:0.6rem 0.4rem;text-align:center;font-family:'Share Tech Mono',monospace;font-size:0.68rem;color:{p};letter-spacing:1px;}}
.agent-card:nth-child(1){{animation:agentPulse 1.2s 0.0s ease-in-out infinite;}}
.agent-card:nth-child(2){{animation:agentPulse 1.2s 0.3s ease-in-out infinite;}}
.agent-card:nth-child(3){{animation:agentPulse 1.2s 0.6s ease-in-out infinite;}}
.agent-card:nth-child(4){{animation:agentPulse 1.2s 0.9s ease-in-out infinite;}}
@keyframes agentPulse{{0%,100%{{opacity:0.35;}}50%{{opacity:1;box-shadow:0 0 15px {g}0.4);border-color:{p};}}}}
.winner-badge{{background:linear-gradient(135deg,{g}0.2),{g}0.1));border:2px solid {p};border-radius:12px;padding:1rem;text-align:center;font-family:'Orbitron',monospace;color:{p};font-size:1.2rem;font-weight:900;animation:recPulse 2s infinite;}}
.compare-card{{background:rgba(0,5,16,0.8);border:1px solid {g}0.2);border-radius:12px;padding:1rem;margin-bottom:0.5rem;font-family:'Share Tech Mono',monospace;}}
.divider{{height:1px;background:linear-gradient(90deg,transparent,{g}0.4),transparent);margin:1.2rem 0;position:relative;z-index:1;}}
.chip{{background:{g}0.08);border:1px solid {g}0.2);border-radius:20px;padding:0.15rem 0.7rem;font-family:'Share Tech Mono',monospace;font-size:0.7rem;color:{g}0.7);display:inline-block;margin:0.15rem;}}
.footer-text{{text-align:center;font-family:'Share Tech Mono',monospace;color:{g}0.25);font-size:0.62rem;margin-top:2rem;letter-spacing:2px;position:relative;z-index:1;}}
#MainMenu,footer,header{{visibility:hidden;}}
.block-container{{padding-top:0.5rem !important;max-width:1400px !important;}}
.stSelectbox>div>div{{background:rgba(0,5,16,0.9) !important;border:1px solid {g}0.35) !important;border-radius:8px !important;color:{p} !important;font-family:'Share Tech Mono',monospace !important;}}
.stSelectbox>div>div{{background:rgba(0,5,16,0.9) !important;border:1px solid {g}0.35) !important;border-radius:8px !important;color:{p} !important;font-family:'Share Tech Mono',monospace !important;}}
.stSelectbox li{{background:rgba(0,5,16,0.95) !important;color:{p} !important;font-family:'Share Tech Mono',monospace !important;}}
.stSelectbox li:hover{{background:{g}0.2) !important;}}
[data-baseweb="menu"]{{background:rgba(0,5,16,0.98) !important;border:1px solid {g}0.3) !important;}}
[data-baseweb="option"]{{background:rgba(0,5,16,0.95) !important;color:{p} !important;font-family:'Share Tech Mono',monospace !important;}}
[data-baseweb="option"]:hover{{background:{g}0.15) !important;}}
[role="option"]{{color:{p} !important;background:rgba(0,5,16,0.95) !important;}}
[role="option"]:hover{{background:{g}0.15) !important;}}.stTextInput>div>div>input:focus{{border-color:{p} !important;box-shadow:0 0 20px {g}0.3) !important;}}
.stButton>button{{background:linear-gradient(135deg,{g}0.15),rgba(0,200,255,0.1)) !important;border:1px solid {p} !important;color:{p} !important;font-family:'Orbitron',monospace !important;font-weight:700 !important;letter-spacing:2px !important;border-radius:8px !important;transition:all 0.3s ease !important;}}
.stButton>button:hover{{background:linear-gradient(135deg,{g}0.3),rgba(0,200,255,0.2)) !important;box-shadow:0 0 25px {g}0.5) !important;transform:translateY(-2px) !important;}}
label{{font-family:'Share Tech Mono',monospace !important;color:{g}0.6) !important;letter-spacing:1px !important;font-size:0.72rem !important;}}
.stTabs [data-baseweb="tab-list"]{{background:rgba(0,5,16,0.8) !important;border-radius:10px !important;border:1px solid {g}0.2) !important;}}
.stTabs [data-baseweb="tab"]{{font-family:'Orbitron',monospace !important;font-size:0.7rem !important;color:{g}0.5) !important;padding:0.5rem 1.2rem !important;}}
.stTabs [aria-selected="true"]{{background:{g}0.15) !important;color:{p} !important;border-radius:8px !important;}}
.stNumberInput>div>div>input{{background:rgba(0,5,16,0.9) !important;border:1px solid {g}0.35) !important;border-radius:8px !important;color:#fff !important;font-family:'Share Tech Mono',monospace !important;}}
.stSelectbox div[data-baseweb="select"] span{{color:#ffffff !important;}}
.stSelectbox svg{{fill:{p} !important;}}
div[data-testid="stMetricValue"]{{color:#ffffff !important;}}
p, div, span, li{{color:#ffffff;}}
.stMarkdown p{{color:#ffffff !important;}}
.data-key{{color:{g}0.6) !important;}}
.data-val{{color:#ffffff !important;font-weight:bold;}}
.metric-label{{color:{g}0.6) !important;}}
</style>""", unsafe_allow_html=True)

def plot_chart(prices, ohlc, ticker, p, g, currency="$"):
    tab1, tab2, tab3 = st.tabs(["📈  LINE", "🕯  CANDLESTICK", "📊  VOLUME"])
    with tab1:
        if prices:
            fig = go.Figure()
            fig.add_trace(go.Scatter(y=prices, mode="lines", line=dict(color=p, width=2.5), fill="tozeroy", fillcolor=g+"0.07)"))
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,5,16,0.6)",
                font=dict(family="Share Tech Mono", color=g+"0.6)"),
                xaxis=dict(showgrid=True, gridcolor=g+"0.07)", zeroline=False),
                yaxis=dict(showgrid=True, gridcolor=g+"0.07)", zeroline=False, color=g+"0.5)"),
                height=360, margin=dict(l=0,r=0,t=10,b=0), hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)
    with tab2:
        if ohlc.get("close"):
            fig = go.Figure(go.Candlestick(
                x=list(range(len(ohlc["close"]))),
                open=ohlc.get("open",[]), high=ohlc.get("high",[]),
                low=ohlc.get("low",[]), close=ohlc.get("close",[]),
                increasing_line_color="#00ff9d", decreasing_line_color="#ff0066",
                increasing_fillcolor="rgba(0,255,157,0.3)", decreasing_fillcolor="rgba(255,0,102,0.3)"
            ))
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,5,16,0.6)",
                font=dict(family="Share Tech Mono", color=g+"0.6)"),
                xaxis=dict(showgrid=True, gridcolor=g+"0.07)", rangeslider=dict(visible=False)),
                yaxis=dict(showgrid=True, gridcolor=g+"0.07)", color=g+"0.5)"),
                height=380, margin=dict(l=0,r=0,t=10,b=0))
            st.plotly_chart(fig, use_container_width=True)
    with tab3:
        if ohlc.get("volume") and ohlc.get("close"):
            closes = ohlc["close"]
            volumes = ohlc["volume"]
            colors = []
            for i in range(len(closes)):
                if i == 0 or closes[i] is None or closes[i-1] is None:
                    colors.append("rgba(0,255,157,0.6)")
                elif closes[i] >= closes[i-1]:
                    colors.append("rgba(0,255,157,0.6)")
                else:
                    colors.append("rgba(255,0,102,0.6)")
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.65,0.35], vertical_spacing=0.04)
            fig.add_trace(go.Scatter(y=closes, mode="lines", line=dict(color=p, width=2), fill="tozeroy", fillcolor=g+"0.07)", name="Price"), row=1, col=1)
            fig.add_trace(go.Bar(y=volumes, marker_color=colors, name="Volume"), row=2, col=1)
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,5,16,0.6)",
                font=dict(family="Share Tech Mono", color=g+"0.6)"), showlegend=False,
                height=400, margin=dict(l=0,r=0,t=10,b=0), hovermode="x unified")
            fig.update_xaxes(showgrid=True, gridcolor=g+"0.07)", zeroline=False)
            fig.update_yaxes(showgrid=True, gridcolor=g+"0.07)", zeroline=False, color=g+"0.5)")
            st.plotly_chart(fig, use_container_width=True)

if "rec"        not in st.session_state: st.session_state.rec        = "N/A"
if "watchlist"  not in st.session_state: st.session_state.watchlist  = []
if "fg_data"    not in st.session_state: st.session_state.fg_data    = None
if "news_data"  not in st.session_state: st.session_state.news_data  = []
if "stock_news" not in st.session_state: st.session_state.stock_news = []
theme = get_theme(st.session_state.rec)
inject_css(theme)
p = theme["p"]; g = theme["g"]

ASSET_CONFIG = {
    "🇺🇸 US Stocks":  {"market":"US",        "examples":["NVDA","AAPL","TSLA","MSFT","GOOGL"]},
    "🇮🇳 India NSE":  {"market":"NSE",       "examples":["TCS","RELIANCE","INFY","HDFCBANK","WIPRO"]},
    "🇮🇳 India BSE":  {"market":"BSE",       "examples":["TATAMOTORS","WIPRO","BAJFINANCE"]},
    "🇬🇧 London LSE": {"market":"LSE",       "examples":["HSBA","BP","AZN","SHEL","LLOY"]},
    "🇩🇪 Frankfurt":  {"market":"Frankfurt", "examples":["SAP","BMW","SIE","BAYN","VOW3"]},
    "🇯🇵 Tokyo":      {"market":"Tokyo",     "examples":["7203","6758","9984","8306"]},
    "🇭🇰 Hong Kong":  {"market":"HongKong",  "examples":["0700","0941","1299","0005"]},
    "🇸🇬 Singapore":  {"market":"Singapore", "examples":["D05","O39","U11","Z74"]},
    "₿ Crypto":       {"market":"Crypto",    "examples":["BTC-USD","ETH-USD","SOL-USD","BNB-USD"]},
    "💱 Forex":       {"market":"Forex",     "examples":["GBPUSD=X","EURUSD=X","USDINR=X","USDJPY=X"]},
    "🏅 Commodities": {"market":"Commodity", "examples":["GC=F","CL=F","SI=F","NG=F"]},
}

ticker_items = "NVDA&nbsp;▲2.1%&nbsp;&nbsp;·&nbsp;&nbsp;AAPL&nbsp;▼0.8%&nbsp;&nbsp;·&nbsp;&nbsp;BTC&nbsp;▲3.2%&nbsp;&nbsp;·&nbsp;&nbsp;TSLA&nbsp;▲1.5%&nbsp;&nbsp;·&nbsp;&nbsp;GOLD&nbsp;▲0.4%&nbsp;&nbsp;·&nbsp;&nbsp;GBP/USD&nbsp;▼0.2%&nbsp;&nbsp;·&nbsp;&nbsp;TCS&nbsp;▲1.1%&nbsp;&nbsp;·&nbsp;&nbsp;SAP&nbsp;▲0.7%&nbsp;&nbsp;·&nbsp;&nbsp;ETH&nbsp;▲2.8%"
st.markdown(f'<div class="ticker-wrap"><div class="ticker"><span class="ticker-item">{ticker_items}</span><span class="ticker-item">{ticker_items}</span></div></div>', unsafe_allow_html=True)

st.markdown('<div class="hero-title">⬡ FINAGENT GLOBAL</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">[ AI Trading War Room · LangGraph · Groq · Tavily · 11 Markets ]</div>', unsafe_allow_html=True)
st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# LOAD GENERAL NEWS ON STARTUP
if not st.session_state.news_data:
    try:
        nr = requests.get("http://localhost:8000/news/general", timeout=10)
        st.session_state.news_data = nr.json().get("news", [])
    except:
        pass

# MAIN LAYOUT — LEFT + RIGHT
main_left, main_right = st.columns([7, 3])

with main_right:
    st.markdown('<div class="data-panel" style="height:100%;min-height:600px;">'
        + '<div class="panel-title">◈ Live Market Intelligence</div>', unsafe_allow_html=True)

    news_tab1, news_tab2 = st.tabs(["🌍 GLOBAL", "📊 STOCK"])

    with news_tab1:
        if st.session_state.news_data:
            for item in st.session_state.news_data:
                st.markdown(
                    '<div style="padding:0.6rem 0;border-bottom:1px solid rgba(0,255,157,0.1);">'
                    + '<div style="font-family:Share Tech Mono,monospace;font-size:0.75rem;color:#ffffff;line-height:1.4;margin-bottom:0.3rem;">' + item.get("title","") + '</div>'
                    + '<div style="display:flex;justify-content:space-between;">'
                    + '<span style="font-family:Share Tech Mono,monospace;font-size:0.65rem;color:rgba(0,255,157,0.5);">📰 ' + item.get("source","") + '</span>'
                    + '<a href="' + item.get("url","#") + '" target="_blank" style="font-family:Share Tech Mono,monospace;font-size:0.65rem;color:rgba(0,200,255,0.6);text-decoration:none;">READ →</a>'
                    + '</div></div>',
                    unsafe_allow_html=True
                )
        else:
            st.markdown('<div style="font-family:Share Tech Mono,monospace;color:rgba(0,255,157,0.4);text-align:center;padding:2rem;">Loading news...</div>', unsafe_allow_html=True)

        if st.button("🔄 REFRESH", key="refresh_news", use_container_width=True):
            try:
                nr = requests.get("http://localhost:8000/news/general", timeout=10)
                st.session_state.news_data = nr.json().get("news", [])
                st.rerun()
            except:
                pass

    with news_tab2:
        if st.session_state.stock_news:
            for item in st.session_state.stock_news:
                st.markdown(
                    '<div style="padding:0.6rem 0;border-bottom:1px solid rgba(0,255,157,0.1);">'
                    + '<div style="font-family:Share Tech Mono,monospace;font-size:0.75rem;color:#ffffff;line-height:1.4;margin-bottom:0.3rem;">' + item.get("title","") + '</div>'
                    + '<div style="display:flex;justify-content:space-between;">'
                    + '<span style="font-family:Share Tech Mono,monospace;font-size:0.65rem;color:rgba(0,255,157,0.5);">📰 ' + item.get("source","") + '</span>'
                    + '<a href="' + item.get("url","#") + '" target="_blank" style="font-family:Share Tech Mono,monospace;font-size:0.65rem;color:rgba(0,200,255,0.6);text-decoration:none;">READ →</a>'
                    + '</div></div>',
                    unsafe_allow_html=True
                )
        else:
            st.markdown('<div style="font-family:Share Tech Mono,monospace;color:rgba(0,255,157,0.4);text-align:center;padding:2rem;">Analyse a stock to see specific news</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

with main_left:
    tab_single, tab_compare, tab_watchlist, tab_feargreed = st.tabs([
        "🔍 SINGLE STOCK",
        "⚔️ COMPARE",
        "👁 WATCHLIST",
        "😨 FEAR & GREED"
    ])

    with tab_single:    c1,c2,c3 = st.columns([1.5,2,1])
    with c1:
        asset_choice = st.selectbox("MARKET", list(ASSET_CONFIG.keys()))
    cfg = ASSET_CONFIG[asset_choice]
    market = cfg["market"]
    with c2:
        ticker_input = st.text_input("SYMBOL", placeholder=" · ".join(cfg["examples"][:4]), key="single_ticker")
    with c3:
        st.markdown("<br>", unsafe_allow_html=True)
        analyse_btn = st.button("⬡ ANALYSE", type="primary", use_container_width=True, key="single_btn")

    st.markdown("".join([f'<span class="chip">{e}</span>' for e in cfg["examples"]]), unsafe_allow_html=True)

    if analyse_btn and ticker_input:
        st.markdown("""<div class="agent-grid">
            <div class="agent-card">◉ NEWS SCRAPER</div>
            <div class="agent-card">◉ SENTIMENT AI</div>
            <div class="agent-card">◉ FIN DATA</div>
            <div class="agent-card">◉ REPORT GEN</div>
        </div>""", unsafe_allow_html=True)

        with st.spinner("AGENTS PROCESSING..."):
            try:
                res = requests.post("http://localhost:8000/analyse", json={"ticker":ticker_input.upper(),"market":market}, timeout=60)
                data = res.json()
            except Exception as e:
                st.error(f"ERROR: {e}"); st.stop()
# Fetch stock specific news
        try:
            snr = requests.get(f"http://localhost:8000/news/{ticker_input.upper()}", timeout=10)
            st.session_state.stock_news = snr.json().get("news", [])
        except:
            pass
        report = data.get("report",{})
        sentiment = data.get("sentiment",{})
        fin = data.get("financial_data",{})
        rec = report.get("recommendation","N/A")
        currency = fin.get("currency","$")
        st.session_state.rec = rec

        wl_entry = {"ticker":ticker_input.upper(),"market":market,"price":fin.get("current_price","N/A"),"rec":rec}
        if not any(w["ticker"]==ticker_input.upper() for w in st.session_state.watchlist):
            st.session_state.watchlist.append(wl_entry)

        theme = get_theme(rec)
        inject_css(theme)
        p2 = theme["p"]; g2 = theme["g"]
        sent_color = {"Bullish":"#00ff9d","Bearish":"#ff0066","Neutral":"#ffaa00"}.get(sentiment.get("sentiment",""),"#fff")

        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        cols = st.columns(5)
        metrics = [
            ("RECOMMENDATION", '<span class="rec-value">' + rec + '</span>'),
            ("CONFIDENCE", '<span class="metric-value">' + report.get("confidence","N/A") + '</span>'),
            ("SENTIMENT", '<span class="metric-value" style="color:' + sent_color + ';">' + sentiment.get("sentiment","N/A") + '</span>'),
            ("LIVE PRICE", '<span class="metric-value">' + fin.get("current_price","N/A") + '</span>'),
            ("24H CHANGE", '<span class="metric-value">' + fin.get("change_percent","N/A") + '</span>'),
        ]
        for col,(label,val) in zip(cols,metrics):
            with col:
                st.markdown('<div class="metric-card"><div class="metric-label">' + label + '</div>' + val + '</div>', unsafe_allow_html=True)

        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        cl,cr = st.columns(2)
        with cl:
            st.markdown('<div class="data-panel"><div class="panel-title">◈ Market Data Matrix</div>'
                + '<div class="data-row"><span class="data-key">ASSET</span><span class="data-val">' + fin.get("company_name",ticker_input) + '</span></div>'
                + '<div class="data-row"><span class="data-key">MARKET</span><span class="data-val">' + fin.get("market_label",market) + '</span></div>'
                + '<div class="data-row"><span class="data-key">52W HIGH</span><span class="data-val">' + fin.get("52w_high","N/A") + '</span></div>'
                + '<div class="data-row"><span class="data-key">52W LOW</span><span class="data-val">' + fin.get("52w_low","N/A") + '</span></div>'
                + '<div class="data-row"><span class="data-key">DAY HIGH</span><span class="data-val">' + fin.get("day_high","N/A") + '</span></div>'
                + '<div class="data-row"><span class="data-key">DAY LOW</span><span class="data-val">' + fin.get("day_low","N/A") + '</span></div>'
                + '<div class="data-row"><span class="data-key">VOLUME</span><span class="data-val">' + str(fin.get("volume","N/A")) + '</span></div>'
                + '<div class="data-row"><span class="data-key">AI TARGET</span><span class="data-val">' + currency + str(report.get("target_price","N/A")) + '</span></div>'
                + '</div>', unsafe_allow_html=True)
        with cr:
            st.markdown('<div class="data-panel">'
                + '<div class="panel-title">◈ AI Intelligence Report</div>'
                + '<div class="reasoning-text">' + report.get("reasoning","N/A") + '</div><br>'
                + '<div class="panel-title">◈ News Intelligence</div>'
                + '<div class="reasoning-text">' + report.get("news_summary","N/A") + '</div><br>'
                + '<div class="panel-title">◈ Sentiment Signal</div>'
                + '<div style="font-family:Share Tech Mono,monospace;font-size:0.8rem;color:' + sent_color + ';padding:0.5rem;border-left:2px solid ' + sent_color + ';">SCORE: ' + str(sentiment.get("score","N/A")) + ' · ' + sentiment.get("summary","N/A") + '</div>'
                + '</div>', unsafe_allow_html=True)

        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="data-panel"><div class="panel-title">◈ Risk Vectors</div>', unsafe_allow_html=True)
        rc = st.columns(2)
        for i,risk in enumerate(report.get("risks",[])):
            with rc[i%2]:
                st.markdown('<div class="risk-badge">⚠ ' + risk + '</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        plot_chart(fin.get("price_history",[]), fin.get("ohlc",{}), ticker_input, p2, g2, currency)

        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        import datetime
        report_text = "FINAGENT GLOBAL REPORT\n" + "="*50 + "\n"
        report_text += "Asset: " + fin.get("company_name",ticker_input) + "\n"
        report_text += "Market: " + fin.get("market_label",market) + "\n"
        report_text += "Date: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M") + "\n\n"
        report_text += "RECOMMENDATION: " + rec + "\n"
        report_text += "CONFIDENCE: " + report.get("confidence","N/A") + "\n"
        report_text += "LIVE PRICE: " + fin.get("current_price","N/A") + "\n"
        report_text += "24H CHANGE: " + fin.get("change_percent","N/A") + "\n"
        report_text += "AI TARGET: " + currency + str(report.get("target_price","N/A")) + "\n\n"
        report_text += "SENTIMENT: " + sentiment.get("sentiment","N/A") + "\n\n"
        report_text += "AI REASONING:\n" + report.get("reasoning","N/A") + "\n\n"
        report_text += "NEWS SUMMARY:\n" + report.get("news_summary","N/A") + "\n\n"
        report_text += "RISKS:\n" + "\n".join(["• "+r for r in report.get("risks",[])]) + "\n"
        report_text += "="*50 + "\nNOT FINANCIAL ADVICE · FINAGENT GLOBAL\n"
        st.download_button("📄 EXPORT REPORT", data=report_text,
            file_name="finagent_" + ticker_input.upper() + "_" + market + ".txt",
            mime="text/plain", use_container_width=True)

with tab_compare:
    st.markdown('<div class="data-panel"><div class="panel-title">◈ Multi-Stock Battle Arena</div>', unsafe_allow_html=True)
    cc1,cc2 = st.columns(2)
    with cc1:
        cmp_market = st.selectbox("MARKET", list(ASSET_CONFIG.keys()), key="cmp_market")
    with cc2:
        cmp_tickers = st.text_input("SYMBOLS (comma separated)", placeholder="NVDA, AAPL, TSLA", key="cmp_tickers")
    cmp_btn = st.button("⚔️ COMPARE", type="primary", key="cmp_btn")
    st.markdown('</div>', unsafe_allow_html=True)

    if cmp_btn and cmp_tickers:
        tickers_list = [t.strip().upper() for t in cmp_tickers.split(",") if t.strip()][:4]
        with st.spinner("BATTLE ANALYSIS RUNNING..."):
            try:
                res = requests.post("http://localhost:8000/compare",
                    json={"tickers":tickers_list,"market":ASSET_CONFIG[cmp_market]["market"]}, timeout=60)
                cmp_data = res.json()
            except Exception as e:
                st.error(f"ERROR: {e}"); st.stop()

        analysis = cmp_data.get("analysis",{})
        stocks = cmp_data.get("stocks",[])
        winner = analysis.get("winner","N/A")

        st.markdown('<div class="winner-badge">🏆 WINNER: ' + winner + '</div>', unsafe_allow_html=True)
        st.markdown('<div style="font-family:Share Tech Mono,monospace;color:rgba(255,255,255,0.7);font-size:0.82rem;padding:1rem;border-left:2px solid ' + p + ';">' + analysis.get("winner_reason","") + '</div>', unsafe_allow_html=True)
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

        cols = st.columns(len(stocks))
        colors_list = ["#00ff9d","#00c8ff","#ff00ff","#ffaa00"]
        for col,stock in zip(cols,stocks):
            with col:
                is_winner = stock.get("symbol","").split(".")[0] == winner
                border = p if is_winner else "rgba(255,255,255,0.1)"
                st.markdown('<div class="compare-card" style="border-color:' + border + ';">'
                    + '<div style="font-family:Orbitron,monospace;color:' + (p if is_winner else "#fff") + ';font-size:1rem;font-weight:700;margin-bottom:0.5rem;">' + ("🏆 " if is_winner else "") + stock.get("symbol","") + '</div>'
                    + '<div style="font-family:Share Tech Mono,monospace;font-size:0.75rem;color:rgba(255,255,255,0.5);margin-bottom:0.5rem;">' + stock.get("name","")[:25] + '</div>'
                    + '<div style="font-family:Share Tech Mono,monospace;font-size:0.82rem;">💰 ' + str(stock.get("price","N/A")) + '<br>📈 ' + str(stock.get("change","N/A")) + '<br>🗓 1mo: ' + str(stock.get("perf_1mo","N/A")) + '</div>'
                    + '</div>', unsafe_allow_html=True)

        if stocks:
            fig = go.Figure()
            for i,stock in enumerate(stocks):
                if stock.get("closes"):
                    closes = stock["closes"]
                    norm = [c/closes[0]*100 for c in closes if c]
                    fig.add_trace(go.Scatter(y=norm, mode="lines", name=stock.get("symbol",""), line=dict(color=colors_list[i%4], width=2)))
            fig.update_layout(
                title=dict(text="◈ NORMALISED PERFORMANCE (Base 100)", font=dict(family="Orbitron",color=p,size=11)),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,5,16,0.6)",
                font=dict(family="Share Tech Mono",color="rgba(0,255,157,0.6)"),
                xaxis=dict(showgrid=True,gridcolor="rgba(0,255,157,0.07)",zeroline=False),
                yaxis=dict(showgrid=True,gridcolor="rgba(0,255,157,0.07)",zeroline=False),
                height=350, margin=dict(l=0,r=0,t=40,b=0), legend=dict(bgcolor="rgba(0,0,0,0.5)")
            )
            st.plotly_chart(fig, use_container_width=True)
        st.markdown('<div class="reasoning-text" style="margin-top:1rem;">' + analysis.get("summary","") + '</div>', unsafe_allow_html=True)

with tab_portfolio:
    st.markdown('<div class="data-panel"><div class="panel-title">◈ Portfolio Analyser</div>', unsafe_allow_html=True)
    holdings = []
    for i in range(5):
        pc1,pc2,pc3 = st.columns([2,1,1])
        with pc1:
            sym = st.text_input("SYMBOL " + str(i+1), placeholder=["NVDA","AAPL","TSLA","MSFT","GOOGL"][i], key="pf_sym_"+str(i))
        with pc2:
            alloc = st.number_input("ALLOCATION %", min_value=0.0, max_value=100.0, value=20.0, key="pf_alloc_"+str(i))
        with pc3:
            shares = st.number_input("SHARES", min_value=0.0, value=10.0, key="pf_shares_"+str(i))
        if sym:
            holdings.append({"symbol":sym.upper(),"allocation":alloc,"shares":shares})
    st.markdown('</div>', unsafe_allow_html=True)
    pf_btn = st.button("📁 ANALYSE PORTFOLIO", type="primary", key="pf_btn")

    if pf_btn and holdings:
        with st.spinner("PORTFOLIO ANALYSIS RUNNING..."):
            try:
                res = requests.post("http://localhost:8000/portfolio", json={"holdings":holdings}, timeout=90)
                pf_data = res.json()
            except Exception as e:
                st.error(f"ERROR: {e}"); st.stop()

        analysis = pf_data.get("analysis",{})
        stocks = pf_data.get("stocks",[])
        score = analysis.get("overall_score",0)
        score_color = "#00ff9d" if score>=7 else "#ffaa00" if score>=5 else "#ff0066"

        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        pc1,pc2,pc3,pc4 = st.columns(4)
        with pc1:
            st.markdown('<div class="metric-card"><div class="metric-label">PORTFOLIO SCORE</div><div class="metric-value" style="color:' + score_color + ';font-size:2rem;">' + str(score) + '/10</div></div>', unsafe_allow_html=True)
        with pc2:
            st.markdown('<div class="metric-card"><div class="metric-label">RATING</div><div class="metric-value">' + analysis.get("overall_rating","N/A") + '</div></div>', unsafe_allow_html=True)
        with pc3:
            st.markdown('<div class="metric-card"><div class="metric-label">RISK LEVEL</div><div class="metric-value">' + analysis.get("risk_level","N/A") + '</div></div>', unsafe_allow_html=True)
        with pc4:
            st.markdown('<div class="metric-card"><div class="metric-label">DIVERSIFICATION</div><div class="metric-value">' + str(analysis.get("diversification_score","N/A")) + '/10</div></div>', unsafe_allow_html=True)

        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        pl,pr = st.columns(2)
        with pl:
            rows = ""
            for s in stocks:
                clr = "#00ff9d" if "+" in str(s.get("perf_3mo","")) else "#ff0066"
                rows += '<div class="data-row"><span class="data-key">' + s.get("symbol","") + '</span><span class="data-val" style="color:' + clr + ';">' + str(s.get("current_price","N/A")) + ' · ' + str(s.get("perf_3mo","N/A")) + ' · ' + str(s.get("drawdown","N/A")) + '</span></div>'
            st.markdown('<div class="data-panel"><div class="panel-title">◈ Holdings Performance</div>' + rows + '</div>', unsafe_allow_html=True)
        with pr:
            rebal = "🔴 YES" if analysis.get("rebalancing_needed") else "🟢 NO"
            recs = "".join(['<div style="padding:0.3rem 0;border-bottom:1px solid rgba(0,255,157,0.1);">▶ ' + r + '</div>' for r in analysis.get("recommendations",[])])
            st.markdown('<div class="data-panel">'
                + '<div class="panel-title">◈ AI Recommendations</div>'
                + '<div class="reasoning-text">' + analysis.get("summary","N/A") + '</div><br>'
                + '<div class="panel-title">◈ Action Items</div>'
                + '<div style="font-family:Share Tech Mono,monospace;font-size:0.8rem;color:rgba(255,255,255,0.8);">' + recs + '</div><br>'
                + '<div class="data-row"><span class="data-key">REBALANCING</span><span class="data-val">' + rebal + '</span></div>'
                + '<div class="data-row"><span class="data-key">BEST PERFORMER</span><span class="data-val" style="color:#00ff9d;">' + analysis.get("best_performer","N/A") + '</span></div>'
                + '<div class="data-row"><span class="data-key">WORST PERFORMER</span><span class="data-val" style="color:#ff0066;">' + analysis.get("worst_performer","N/A") + '</span></div>'
                + '</div>', unsafe_allow_html=True)

        if stocks:
            fig = go.Figure(go.Pie(
                labels=[s["symbol"] for s in stocks],
                values=[s.get("allocation",20) for s in stocks],
                hole=0.6,
                marker=dict(colors=["#00ff9d","#00c8ff","#ff00ff","#ffaa00","#ff6699"],
                    line=dict(color="#000510",width=2))
            ))
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Share Tech Mono",color="rgba(0,255,157,0.7)"),
                height=320, margin=dict(l=0,r=0,t=20,b=0),
                legend=dict(bgcolor="rgba(0,0,0,0.5)",font=dict(color="rgba(0,255,157,0.7)")))
            st.plotly_chart(fig, use_container_width=True)

with tab_watchlist:
    st.markdown('<div class="data-panel"><div class="panel-title">◈ Watchlist</div>', unsafe_allow_html=True)
    if not st.session_state.watchlist:
        st.markdown('<div style="font-family:Share Tech Mono,monospace;color:rgba(0,255,157,0.4);text-align:center;padding:2rem;">No stocks yet — analyse something first!</div>', unsafe_allow_html=True)
    else:
        for i,item in enumerate(st.session_state.watchlist):
            rec_c = {"BUY":"#00ff9d","SELL":"#ff0066","HOLD":"#ffaa00"}.get(item.get("rec",""),"#fff")
            wc1,wc2,wc3,wc4 = st.columns([2,1,1,1])
            with wc1:
                st.markdown('<div style="font-family:Orbitron,monospace;color:#fff;font-weight:700;padding:0.5rem 0;">' + item["ticker"] + '</div>', unsafe_allow_html=True)
            with wc2:
                st.markdown('<div style="font-family:Share Tech Mono,monospace;color:rgba(0,255,157,0.5);padding:0.5rem 0;">' + item["market"] + '</div>', unsafe_allow_html=True)
            with wc3:
                st.markdown('<div style="font-family:Share Tech Mono,monospace;color:#fff;padding:0.5rem 0;">' + str(item["price"]) + '</div>', unsafe_allow_html=True)
            with wc4:
                st.markdown('<div style="font-family:Orbitron,monospace;color:' + rec_c + ';font-weight:700;padding:0.5rem 0;">' + item["rec"] + '</div>', unsafe_allow_html=True)
            st.markdown('<div style="height:1px;background:rgba(0,255,157,0.1);margin:0.2rem 0;"></div>', unsafe_allow_html=True)
    if st.button("🗑 CLEAR WATCHLIST", key="clear_wl"):
        st.session_state.watchlist = []
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

with tab_feargreed:
    st.markdown('<div class="data-panel"><div class="panel-title">◈ Global Market Fear & Greed Index</div>', unsafe_allow_html=True)
    fg_btn = st.button("📡 FETCH LIVE INDEX", type="primary", key="fg_btn")
    st.markdown('</div>', unsafe_allow_html=True)

    if fg_btn:
        with st.spinner("CALCULATING FEAR & GREED..."):
            try:
                res = requests.get("http://localhost:8000/feargreed", timeout=30)
                st.session_state.fg_data = res.json()
            except Exception as e:
                st.error(f"ERROR: {e}")

    if st.session_state.fg_data:
        fg = st.session_state.fg_data
        score = fg.get("score", 50)
        label = fg.get("label", "Neutral")
        fg_color = "#00ff9d" if score>=55 else "#ff0066" if score<=45 else "#ffaa00"

        fig = go.Figure(go.Indicator(
            mode="gauge+number", value=score,
            domain=dict(x=[0,1],y=[0,1]),
            title=dict(text="<b>" + label + "</b>", font=dict(family="Orbitron",color=fg_color,size=20)),
            gauge=dict(
                axis=dict(range=[0,100], tickfont=dict(family="Share Tech Mono",color="rgba(0,255,157,0.5)"),tickcolor="rgba(0,255,157,0.3)"),
                bar=dict(color=fg_color,thickness=0.3),
                bgcolor="rgba(0,5,16,0.8)", bordercolor="rgba(0,255,157,0.2)",
                steps=[
                    dict(range=[0,25],color="rgba(255,0,102,0.3)"),
                    dict(range=[25,45],color="rgba(255,100,0,0.2)"),
                    dict(range=[45,55],color="rgba(255,170,0,0.2)"),
                    dict(range=[55,75],color="rgba(0,200,100,0.2)"),
                    dict(range=[75,100],color="rgba(0,255,157,0.3)"),
                ],
                threshold=dict(line=dict(color=fg_color,width=4),thickness=0.8,value=score)
            ),
            number=dict(font=dict(family="Orbitron",color=fg_color,size=40))
        ))
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Share Tech Mono",color="rgba(0,255,157,0.6)"),
            height=380, margin=dict(l=30,r=30,t=30,b=10))
        st.plotly_chart(fig, use_container_width=True)

        fgc1,fgc2,fgc3 = st.columns(3)
        with fgc1:
            vix_color = "#ff0066" if fg.get("vix",20)>25 else "#00ff9d"
            st.markdown('<div class="metric-card"><div class="metric-label">VIX FEAR INDEX</div><div class="metric-value" style="color:' + vix_color + ';">' + str(fg.get("vix","N/A")) + '</div></div>', unsafe_allow_html=True)
        with fgc2:
            sp_color = "#00ff9d" if (fg.get("sp500_momentum",0) or 0)>0 else "#ff0066"
            st.markdown('<div class="metric-card"><div class="metric-label">S&P500 MOMENTUM</div><div class="metric-value" style="color:' + sp_color + ';">' + str(fg.get("sp500_momentum","N/A")) + '%</div></div>', unsafe_allow_html=True)
        with fgc3:
            btc_color = "#00ff9d" if (fg.get("btc_change",0) or 0)>0 else "#ff0066"
            st.markdown('<div class="metric-card"><div class="metric-label">BTC 5D CHANGE</div><div class="metric-value" style="color:' + btc_color + ';">' + str(fg.get("btc_change","N/A")) + '%</div></div>', unsafe_allow_html=True)
# RAG BADGE
        rag = data.get("rag_context", {})
        rag_total = rag.get("total_stored", 0)
        rag_fresh = rag.get("freshly_stored", 0)
        rag_insight = report.get("rag_insight", "")
        st.markdown(
            '<div style="background:rgba(0,200,255,0.08);border:1px solid rgba(0,200,255,0.3);border-radius:10px;padding:0.8rem 1.2rem;font-family:Share Tech Mono,monospace;font-size:0.8rem;margin-bottom:1rem;">'
            + '<span style="color:#00c8ff;font-family:Orbitron,monospace;font-size:0.7rem;letter-spacing:2px;">◈ RAG · VECTOR DB · CHROMADB</span><br>'
            + '<span style="color:rgba(255,255,255,0.8);">📦 Total embeddings stored: <b style="color:#00c8ff;">' + str(rag_total) + '</b> &nbsp;|&nbsp; '
            + '✨ Fresh articles embedded: <b style="color:#00c8ff;">' + str(rag_fresh) + '</b> &nbsp;|&nbsp; '
            + '🧠 Model: <b style="color:#00c8ff;">all-MiniLM-L6-v2</b></span><br>'
            + '<span style="color:rgba(255,255,255,0.7);font-size:0.75rem;">💡 ' + rag_insight + '</span>'
            + '</div>',
            unsafe_allow_html=True
        )
        st.markdown('<div class="data-panel" style="margin-top:1rem;"><div class="panel-title">◈ Index Interpretation</div>'
            + '<div style="font-family:Share Tech Mono,monospace;font-size:0.82rem;color:rgba(255,255,255,0.8);line-height:2;">'
            + '<span style="color:#ff0066;">0-25 = Extreme Fear</span> · Market oversold · Potential buying opportunity<br>'
            + '<span style="color:#ff6600;">25-45 = Fear</span> · Cautious sentiment · Watch for reversal<br>'
            + '<span style="color:#ffaa00;">45-55 = Neutral</span> · Balanced market · Follow stock analysis<br>'
            + '<span style="color:#00c896;">55-75 = Greed</span> · Bullish momentum · Trend following works<br>'
            + '<span style="color:#00ff9d;">75-100 = Extreme Greed</span> · Market overbought · Consider profits'
            + '</div></div>', unsafe_allow_html=True)

st.markdown('<div class="footer-text">⬡ FINAGENT GLOBAL · AI TRADING WAR ROOM · LANGGRAPH + GROQ + TAVILY · NOT FINANCIAL ADVICE ⬡</div>', unsafe_allow_html=True)