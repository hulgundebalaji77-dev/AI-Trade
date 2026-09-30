import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- Page Config ---
st.set_page_config(
    page_title="लक्ष्य AI - ऑटो पेपर ट्रेडिंग टर्मिनल",
    page_icon="🤖",
    layout="wide"
)

# ऑटो रिफ्रेश: दर 10 सेकंदाला पेज ऑटोमॅटिक रिफ्रेश होऊन बॉट निर्णय घेईल
st_autorefresh(interval=10 * 1000, key="auto_market_bot")

st.markdown("""
    <style>
        .stApp { background-color: #080c14; color: #f8fafc; }
        div[data-testid="stMetricValue"] { font-size: 22px; font-weight: 800; }
    </style>
""", unsafe_allow_html=True)

TICKER_MAP = {
    'NIFTY 50': '^NSEI',
    'BANK NIFTY': '^NSEBANK',
    'RELIANCE': 'RELIANCE.NS',
    'TCS': 'TCS.NS',
    'HDFC BANK': 'HDFCBANK.NS'
}

# Session State
if 'capital' not in st.session_state:
    st.session_state.capital = 100000.00
if 'initial_capital' not in st.session_state:
    st.session_state.initial_capital = 100000.00
if 'journal' not in st.session_state:
    st.session_state.journal = []
if 'trade_id' not in st.session_state:
    st.session_state.trade_id = 101
if 'active_trade' not in st.session_state:
    st.session_state.active_trade = None
if 'auto_mode' not in st.session_state:
    st.session_state.auto_mode = True  # ऑटो बॉट चालू/बंद स्विच

def fetch_data(symbol):
    try:
        t = yf.Ticker(symbol)
        df = t.history(period="1d", interval="5m")
        if df.empty or len(df) < 5:
            df = t.history(period="5d", interval="5m")
        return df
    except:
        return pd.DataFrame()

def get_indicators(df):
    if df.empty:
        return df
    c = df['Close']
    df['EMA9'] = c.ewm(span=9, adjust=False).mean()
    df['EMA21'] = c.ewm(span=21, adjust=False).mean()
    delta = c.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['RSI'] = 100 - (100 / (1 + rs))
    df['RSI'] = df['RSI'].fillna(50.0)
    return df

# Header
c1, c2 = st.columns([3, 1])
with c1:
    st.markdown("## 🤖 लक्ष्य AI ऑटोमॅटिक पेपर ट्रेडिंग बॉट")
    st.caption("100% मानवरहित सिमुलेशन (Auto Buy, Auto Sell & Auto Exit)")
with c2:
    st.markdown(f"*वेळ:* {datetime.now().strftime('%H:%M:%S')}")
    st.session_state.auto_mode = st.toggle("ऑटो रोबोट चालू ठेवा (Auto Mode)", value=st.session_state.auto_mode)

# KPI Row
net_pnl = st.session_state.capital - st.session_state.initial_capital
net_pct = (net_pnl / st.session_state.initial_capital) * 100
total_t = len(st.session_state.journal)
wins = sum(1 for x in st.session_state.journal if x['Status'] == 'WIN')
losses = sum(1 for x in st.session_state.journal if x['Status'] == 'LOSS')
win_rate = (wins / total_t * 100) if total_t > 0 else 0

m1, m2, m3, m4 = st.columns(4)
m1.metric("शिल्लक भांडवल", f"₹{st.session_state.capital:,.2f}")
m2.metric("चालू नफा/तोटा (P&L)", f"{'+' if net_pnl >= 0 else ''}₹{net_pnl:,.2f}", f"{net_pct:.2f}%")
m3.metric("विन रेट", f"{win_rate:.1f}%", f"{wins}W / {losses}L")
m4.metric("एकूण पूर्ण ट्रेड्स", total_t)

st.divider()

col_left, col_right = st.columns([2.2, 1])

with col_left:
    sel_symbol = st.selectbox("स्टॉक निवडा", list(TICKER_MAP.keys()), index=0)
    df = fetch_data(TICKER_MAP[sel_symbol])
    
    if not df.empty:
        df = get_indicators(df)
        curr_price = float(df['Close'].iloc[-1])
        ema9 = float(df['EMA9'].iloc[-1])
        ema21 = float(df['EMA21'].iloc[-1])
        rsi = float(df['RSI'].iloc[-1])
        
        st.markdown(f"### {sel_symbol} : ₹{curr_price:,.2f}")

        # Candle chart
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA9'], line=dict(color='#38bdf8'), name='EMA 9'))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA21'], line=dict(color='#f59e0b'), name='EMA 21'))
        fig.update_layout(template="plotly_dark", height=330, margin=dict(l=10, r=10, t=10, b=10), xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # सिस्टीम सिग्नल
        if ema9 > ema21 and rsi > 52:
            signal = "BUY"
        elif ema9 < ema21 and rsi < 48:
            signal = "SELL"
        else:
            signal = "WAIT"

        # --- ऑटोमॅटिक पेपर ट्रेड लॉजिक ---
        if st.session_state.auto_mode:
            # १. चालू ट्रेड तपासणे आणि आपोआप बाहेर पडणे (Auto SL / Target)
            if st.session_state.active_trade is not None:
                t = st.session_state.active_trade
                if t['Symbol'] == sel_symbol:
                    diff = (curr_price - t['Entry']) if t['Type'] == 'BUY' else (t['Entry'] - curr_price)
                    
                    # SL किंवा टार्गेट हिट झाल्यास
                    if (t['Type'] == 'BUY' and curr_price <= t['SL']) or (t['Type'] == 'SELL' and curr_price >= t['SL']):
                        # SL Hit
                        pnl = diff * t['Qty']
                        st.session_state.capital += pnl
                        st.session_state.journal.insert(0, {
                            'ID': t['ID'], 'Time': datetime.now().strftime("%H:%M:%S"), 'Symbol': t['Symbol'],
                            'Type': t['Type'], 'Qty': t['Qty'], 'Entry': t['Entry'], 'Exit': curr_price,
                            'P&L': round(pnl, 2), 'Status': 'LOSS', 'Reason': 'Auto SL Hit'
                        })
                        st.session_state.active_trade = None
                    elif (t['Type'] == 'BUY' and curr_price >= t['Target']) or (t['Type'] == 'SELL' and curr_price <= t['Target']):
                        # Target Hit
                        pnl = diff * t['Qty']
                        st.session_state.capital += pnl
                        st.session_state.journal.insert(0, {
                            'ID': t['ID'], 'Time': datetime.now().strftime("%H:%M:%S"), 'Symbol': t['Symbol'],
                            'Type': t['Type'], 'Qty': t['Qty'], 'Entry': t['Entry'], 'Exit': curr_price,
                            'P&L': round(pnl, 2), 'Status': 'WIN', 'Reason': 'Auto Target Hit'
                        })
                        st.session_state.active_trade = None

            # २. जर कोणताही ट्रेड चालू नसेल आणि सिग्नल आला तर आपोआप नवीन ट्रेड सुरू करणे (Auto Entry)
            elif st.session_state.active_trade is None and signal in ['BUY', 'SELL']:
                sl_gap = 20.0
                tgt_gap = 40.0
                st.session_state.active_trade = {
                    'ID': f"AUTO-{st.session_state.trade_id}",
                    'Symbol': sel_symbol,
                    'Type': signal,
                    'Qty': 10,
                    'Entry': curr_price,
                    'SL': (curr_price - sl_gap) if signal == 'BUY' else (curr_price + sl_gap),
                    'Target': (curr_price + tgt_gap) if signal == 'BUY' else (curr_price - tgt_gap),
                    'Time': datetime.now().strftime("%H:%M:%S")
                }
                st.session_state.trade_id += 1

with col_right:
    st.subheader("बॉट स्थिती (Bot Status)")
    if st.session_state.auto_mode:
        st.success("🤖 ऑटो बॉट: *चालू (ACTIVE)*\n\nसिग्नल येताच स्वतः ट्रेड घेईल.")
    else:
        st.warning("⏸️ ऑटो बॉट: *बंद (PAUSED)*")

    if st.session_state.active_trade:
        tr = st.session_state.active_trade
        st.info(f"*सक्रिय ट्रेड:* {tr['Symbol']} ({tr['Type']})")
        st.write(f"एंट्री: ₹{tr['Entry']:.2f}")
        st.write(f"SL: ₹{tr['SL']:.2f} | Tgt: ₹{tr['Target']:.2f}")
        live_pnl = ((curr_price - tr['Entry']) if tr['Type'] == 'BUY' else (tr['Entry'] - curr_price)) * tr['Qty']
        st.metric("चालू लाइव्ह P&L", f"₹{live_pnl:,.2f}")
    else:
        st.write("सध्या कोणताही ट्रेड सक्रिय नाही. बॉट योग्य सिग्नलची वाट पाहत आहे...")

st.divider()
st.subheader(f"ऑटोमेटेड ट्रेडिंग जर्नल ({len(st.session_state.journal)} ट्रेड्स)")
if st.session_state.journal:
    st.dataframe(pd.DataFrame(st.session_state.journal), use_container_width=True)
else:
    st.info("अद्याप बॉटने एकही ट्रेड पूर्ण केलेला नाही.")
