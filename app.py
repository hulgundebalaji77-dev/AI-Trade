import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime

# --- Page Configuration ---
st.set_page_config(
    page_title="लक्ष्य AI - रियल लाइव्ह ट्रेडिंग टर्मिनल",
    page_icon="📈",
    layout="wide"
)

# Custom Dark Trading Theme
st.markdown("""
    <style>
        .stApp {
            background-color: #080c14;
            color: #f8fafc;
        }
        div[data-testid="stMetricValue"] {
            font-size: 22px;
            font-weight: 800;
        }
    </style>
""", unsafe_allow_html=True)

# NSE Ticker Mapping (Yahoo Finance Symbols)
TICKER_MAP = {
    'NIFTY 50': '^NSEI',
    'BANK NIFTY': '^NSEBANK',
    'RELIANCE': 'RELIANCE.NS',
    'TCS': 'TCS.NS',
    'HDFC BANK': 'HDFCBANK.NS'
}

# --- State Initialization ---
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

# Fetch Real Market Data from Yahoo Finance
@st.cache_data(ttl=15)  # Cache for 15 seconds to allow live refreshes without hitting rate limits
def fetch_live_data(ticker_symbol, timeframe="5m"):
    try:
        ticker = yf.Ticker(ticker_symbol)
        # Fetch intraday data
        df = ticker.history(period="1d", interval=timeframe)
        if df.empty or len(df) < 5:
            # Fallback to 5 days if market is closed or early morning
            df = ticker.history(period="5d", interval=timeframe)
        return df
    except Exception as e:
        return pd.DataFrame()

# Calculate Technical Indicators
def calculate_indicators(df):
    if df.empty:
        return df
    close = df['Close']
    df['EMA9'] = close.ewm(span=9, adjust=False).mean()
    df['EMA21'] = close.ewm(span=21, adjust=False).mean()

    # 14-period RSI
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['RSI'] = 100 - (100 / (1 + rs))
    df['RSI'] = df['RSI'].fillna(50.0)
    return df

# --- Header Section ---
col_head1, col_head2 = st.columns([3, 1])
with col_head1:
    st.markdown("## 🎯 लक्ष्य AI TRADING BOT (LIVE NSE DATA)")
    st.caption("रिअल-टाइम मार्केट प्राईस आणि ऑटोमेटेड ट्रेडिंग जर्नल")
with col_head2:
    st.markdown(f"*वेळ:* {datetime.now().strftime('%H:%M:%S')}")
    if st.button("🔄 डेटा रिफ्रेश करा (Live Refresh)", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.divider()

# --- KPI Dashboard Row ---
net_pnl = st.session_state.capital - st.session_state.initial_capital
net_pct = (net_pnl / st.session_state.initial_capital) * 100
total_trades = len(st.session_state.journal)
wins = sum(1 for t in st.session_state.journal if t['Status'] == 'WIN')
losses = sum(1 for t in st.session_state.journal if t['Status'] == 'LOSS')
win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0

k1, k2, k3, k4 = st.columns(4)
k1.metric("एकूण भांडवल (Balance)", f"₹{st.session_state.capital:,.2f}")
k2.metric("चालू नफा/तोटा (Net P&L)", f"{'+' if net_pnl >= 0 else ''}₹{net_pnl:,.2f}", f"{net_pct:.2f}%")
k3.metric("विन रेट (Win Rate)", f"{win_rate:.1f}%", f"{wins}W / {losses}L")
k4.metric("एकूण पूर्ण ट्रेड्स", total_trades)

st.divider()

# --- Main Grid: Chart + Terminal ---
col_chart, col_terminal = st.columns([2.2, 1])

with col_chart:
    c_sel1, c_sel2 = st.columns([2, 1])
    selected_name = c_sel1.selectbox("स्टॉक / इंडेक्स निवडा", list(TICKER_MAP.keys()), index=0)
    selected_tf = c_sel2.selectbox("टाइमफ्रेम", ["1m", "5m", "15m"], index=1)
    
    ticker_code = TICKER_MAP[selected_name]
    df = fetch_live_data(ticker_code, selected_tf)

    if not df.empty:
        df = calculate_indicators(df)
        
        current_price = df['Close'].iloc[-1]
        prev_price = df['Close'].iloc[-2] if len(df) > 1 else current_price
        diff_pct = ((current_price - prev_price) / prev_price) * 100

        st.markdown(f"### {selected_name} : ₹{current_price:,.2f} ({'+' if diff_pct >= 0 else ''}{diff_pct:.2f}%)")

        # Plotly Candlestick Chart with Real Data
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df.index,
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name='Candles',
            increasing_line_color='#10b981',
            decreasing_line_color='#ef4444'
        ))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA9'], mode='lines', name='EMA 9', line=dict(color='#38bdf8', width=1.5)))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA21'], mode='lines', name='EMA 21', line=dict(color='#f59e0b', width=1.5)))

        if st.session_state.active_trade and st.session_state.active_trade['Symbol'] == selected_name:
            fig.add_hline(y=st.session_state.active_trade['SL'], line_dash="dash", line_color="#ef4444", annotation_text="SL")
            fig.add_hline(y=st.session_state.active_trade['Target'], line_dash="dash", line_color="#10b981", annotation_text="Target")

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#060911",
            plot_bgcolor="#060911",
            xaxis_rangeslider_visible=False,
            height=340,
            margin=dict(l=10, r=10, t=10, b=10)
        )
        st.plotly_chart(fig, use_container_width=True)

        # Telemetry Indicators
        ema9_val = df['EMA9'].iloc[-1]
        ema21_val = df['EMA21'].iloc[-1]
        rsi_val = df['RSI'].iloc[-1]

        t1, t2, t3, t4 = st.columns(4)
        t1.write(f"*EMA 9:* ₹{ema9_val:.2f}")
        t2.write(f"*EMA 21:* ₹{ema21_val:.2f}")
        t3.write(f"*RSI (14):* {rsi_val:.1f}")

        if ema9_val > ema21_val and rsi_val > 52:
            signal_state = "BUY"
            t4.success("ट्रेंड: BULLISH 🟢")
        elif ema9_val < ema21_val and rsi_val < 48:
            signal_state = "SELL"
            t4.error("ट्रेंड: BEARISH 🔴")
        else:
            signal_state = "WAIT"
            t4.warning("ट्रेंड: SIDEWAYS ⚪")
    else:
        st.error("रिअल मार्केट डेटा उपलब्ध होत नाही आहे. कृपया काही वेळाने रिफ्रेश करा.")
        current_price = 0.0
        signal_state = "WAIT"

with col_terminal:
    st.subheader("AI सिग्नल व ट्रेड सेटअप")

    if signal_state == "BUY":
        st.success("▲ *BUY (तेजी)* सिग्नल सक्रिय आहे.")
    elif signal_state == "SELL":
        st.error("▼ *SELL (मंदी)* सिग्नल सक्रिय आहे.")
    else:
        st.warning("⏳ *WAIT (थांबा)* - योग्य संधीची वाट पाहा.")

    # Order Form / Active Position
    if st.session_state.active_trade is None:
        qty = st.number_input("ट्रेड संख्या (Qty)", min_value=1, value=10, step=1)
        c_sl, c_tgt = st.columns(2)
        sl_pts = c_sl.number_input("स्टॉप लॉस अंतर (₹)", min_value=1.0, value=20.0)
        tgt_pts = c_tgt.number_input("टार्गेट अंतर (₹)", min_value=1.0, value=40.0)
        reason = st.text_input("रणनीतीचे नाव", value="EMA 9/21 क्रॉसओव्हर")

        btn_c1, btn_c2 = st.columns(2)
        if btn_c1.button("▲ BUY (खरेदी)", use_container_width=True, disabled=(current_price == 0.0)):
            st.session_state.active_trade = {
                'ID': f"LAK-{st.session_state.trade_id}",
                'Symbol': selected_name,
                'Type': 'BUY',
                'Qty': qty,
                'Entry': current_price,
                'SL': current_price - sl_pts,
                'Target': current_price + tgt_pts,
                'Reason': reason
            }
            st.session_state.trade_id += 1
            st.rerun()

        if btn_c2.button("▼ SELL (विक्री)", use_container_width=True, disabled=(current_price == 0.0)):
            st.session_state.active_trade = {
                'ID': f"LAK-{st.session_state.trade_id}",
                'Symbol': selected_name,
                'Type': 'SELL',
                'Qty': qty,
                'Entry': current_price,
                'SL': current_price + sl_pts,
                'Target': current_price - tgt_pts,
                'Reason': reason
            }
            st.session_state.trade_id += 1
            st.rerun()
    else:
        tr = st.session_state.active_trade
        st.info(f"*सक्रिय ट्रेड:* {tr['Symbol']} ({tr['Type']}) | Qty: {tr['Qty']}")
        st.write(f"*एंट्री प्राईस:* ₹{tr['Entry']:.2f}")
        st.write(f"*SL:* ₹{tr['SL']:.2f} | *Target:* ₹{tr['Target']:.2f}")

        # Live PnL
        live_diff = (current_price - tr['Entry']) if tr['Type'] == 'BUY' else (tr['Entry'] - current_price)
        live_pnl = live_diff * tr['Qty']
        st.metric("चालू नफा/तोटा (Live P&L)", f"{'+' if live_pnl >= 0 else ''}₹{live_pnl:,.2f}")

        if st.button("✕ ट्रेड बंद करा (Exit Trade)", use_container_width=True):
            status = "WIN" if live_pnl >= 0 else "LOSS"
            st.session_state.capital += live_pnl
            st.session_state.journal.insert(0, {
                'Trade ID': tr['ID'],
                'Time': datetime.now().strftime("%H:%M:%S"),
                'Symbol': tr['Symbol'],
                'Type': tr['Type'],
                'Qty': tr['Qty'],
                'Entry': f"₹{tr['Entry']:.2f}",
                'Exit': f"₹{current_price:.2f}",
                'P&L (₹)': round(live_pnl, 2),
                'Status': status,
                'Reason': tr['Reason']
            })
            st.session_state.active_trade = None
            st.rerun()

st.divider()

# --- Automated Trading Journal Section ---
st.subheader(f"ऑटोमेटेड ट्रेडिंग जर्नल ({total_trades} ट्रेड्स नोंदवले)")

if len(st.session_state.journal) > 0:
    df_journal = pd.DataFrame(st.session_state.journal)
    st.dataframe(df_journal, use_container_width=True)

    csv_data = df_journal.to_csv(index=False).encode('utf-8')
    c_exp1, c_exp2 = st.columns([1, 4])
    c_exp1.download_button(
        label="📥 CSV डाउनलोड करा",
        data=csv_data,
        file_name=f"Lakshya_Trading_Journal_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime='text/csv'
    )
    if c_exp2.button("🗑️ जर्नल डेटा रीसेट करा"):
        st.session_state.journal = []
        st.session_state.capital = 100000.00
        st.session_state.active_trade = None
        st.rerun()
else:
    st.info("अद्याप एकही ट्रेड बंद झालेला नाही. वरून BUY किंवा SELL करून सिम्युलेटर सुरू करा!")
