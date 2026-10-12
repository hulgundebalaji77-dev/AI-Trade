import streamlit as st
import numpy as np
import pandas as pd
from scipy.stats import norm

# ----------------- पेज कॉन्फिगरेशन -----------------
st.set_page_config(
    page_title="लक्ष्य AI - F&O प्रोबॅबिलिटी डॅशबोर्ड",
    page_icon="📈",
    layout="wide"
)

# ----------------- गणिती इंजिन (Core Engine) -----------------
class FOProbabilityEngine:
    def __init__(self, risk_free_rate=0.065):
        self.r = risk_free_rate

    def black_scholes_prob(self, spot, iv, dte):
        """१. ऑप्शन व्होलॅटिलिटीवर आधारित संभाव्यता"""
        T = max(dte, 1) / 365.0
        if iv <= 0:
            return 50.0, 50.0, 0.0, spot, spot
        
        expected_move = spot * iv * np.sqrt(T)
        upper_band = spot + expected_move
        lower_band = spot - expected_move
        
        # d2 गणना (ITM संपण्याची शक्यता)
        d2 = ((self.r - 0.5 * (iv ** 2)) * T) / (iv * np.sqrt(T))
        p_up = float(norm.cdf(d2) * 100)
        p_down = 100.0 - p_up
        return p_up, p_down, expected_move, lower_band, upper_band

    def pcr_score(self, pcr):
        """२. Put-Call Ratio (PCR) स्कोअर"""
        score = ((pcr - 0.5) / (1.5 - 0.5)) * 100
        return float(np.clip(score, 0, 100))

    def buildup_score(self, price_chg, oi_chg):
        """३. किंमत आणि OI बिल्डअप स्कोअर"""
        if price_chg > 0 and oi_chg > 0:
            return 85.0, "Long Buildup 🟢"
        elif price_chg > 0 and oi_chg <= 0:
            return 65.0, "Short Covering 🟢"
        elif price_chg <= 0 and oi_chg <= 0:
            return 40.0, "Long Unwinding 🔴"
        else:
            return 15.0, "Short Buildup 🔴"

    def max_pain_drift(self, spot, max_pain):
        """४. मॅक्स पेन दिशेने खेचला जाणारा कल"""
        diff_pct = ((max_pain - spot) / spot) * 100
        drift_score = 50.0 + (diff_pct * 5)
        return float(np.clip(drift_score, 10, 90))

    def evaluate_universe(self, stocks_data, dte=14):
        results = []
        for s in stocks_data:
            bs_up, bs_down, exp_move, l_range, u_range = self.black_scholes_prob(
                s["spot"], s["iv"], dte
            )
            pcr_sc = self.pcr_score(s["pcr"])
            buildup_sc, regime = self.buildup_score(s["price_chg"], s["oi_chg"])
            mp_sc = self.max_pain_drift(s["spot"], s["max_pain"])
            
            # एकत्रित वेटेड संभाव्यता (Ensemble Model)
            bullish_prob = (
                (buildup_sc * 0.35) + 
                (pcr_sc * 0.25) + 
                (bs_up * 0.20) + 
                (mp_sc * 0.20)
            )
            bearish_prob = 100.0 - bullish_prob
            
            # अंतिम सिग्नल वर्गीकरण
            if bullish_prob >= 70:
                signal = "STRONG BULLISH"
            elif bullish_prob >= 55:
                signal = "MILD BULLISH"
            elif bullish_prob <= 30:
                signal = "STRONG BEARISH"
            elif bullish_prob <= 45:
                signal = "MILD BEARISH"
            else:
                signal = "NEUTRAL"

            results.append({
                "शेअर (Symbol)": s["symbol"],
                "किंमत (Spot)": round(s["spot"], 2),
                "तेजी % (Bullish)": round(bullish_prob, 1),
                "मंदी % (Bearish)": round(bearish_prob, 1),
                "सिग्नल (Signal)": signal,
                "कल (Regime)": regime,
                "अपेक्षित रेंज": f"{int(l_range)} - {int(u_range)}",
                "PCR": s["pcr"],
                "Max Pain": s["max_pain"]
            })

        df = pd.DataFrame(results).sort_values(by="तेजी % (Bullish)", ascending=False)
        return df

# ----------------- STREAMLIT UI -----------------
st.title("🎯 F&O संभाव्यता (Probability) ॲनालायझर")
st.markdown("हे मॉडेल **Black-Scholes, PCR, Price-OI Buildup आणि Max Pain** एकत्र करून अंतिम संभाव्यता ठरवते.")

# साइडबार कंट्रोल्स
st.sidebar.header("⚙️ सेटिंग्ज")
dte = st.sidebar.slider("एक्सपायरीसाठी दिवस (Days to Expiry)", min_value=1, max_value=30, value=14)

# नमुना डेटाबेस
market_data = [
    {"symbol": "RELIANCE",   "spot": 2980.0, "iv": 0.21, "price_chg": 1.5,  "oi_chg": 6.2,  "pcr": 1.35, "max_pain": 3020},
    {"symbol": "TCS",        "spot": 3950.0, "iv": 0.18, "price_chg": -1.2, "oi_chg": 4.5,  "pcr": 0.65, "max_pain": 3900},
    {"symbol": "HDFCBANK",   "spot": 1640.0, "iv": 0.19, "price_chg": 0.8,  "oi_chg": -1.5, "pcr": 1.05, "max_pain": 1650},
    {"symbol": "INFY",       "spot": 1820.0, "iv": 0.24, "price_chg": -1.8, "oi_chg": -3.2, "pcr": 0.72, "max_pain": 1800},
    {"symbol": "SBIN",       "spot": 810.0,  "iv": 0.26, "price_chg": 2.2,  "oi_chg": 8.1,  "pcr": 1.40, "max_pain": 830},
    {"symbol": "TATAMOTORS", "spot": 925.0,  "iv": 0.28, "price_chg": -2.4, "oi_chg": 9.5,  "pcr": 0.52, "max_pain": 900}
]

engine = FOProbabilityEngine()
df_final = engine.evaluate_universe(market_data, dte=dte)

# टॉप शेअर्सचे मेट्रिक्स
col1, col2 = st.columns(2)
top_bull = df_final.iloc[0]
top_bear = df_final.iloc[-1]

with col1:
    st.success(f"🚀 Top Bullish: **{top_bull['शेअर (Symbol)']}** ({top_bull['तेजी % (Bullish)']}%)")
with col2:
    st.error(f"📉 Top Bearish: **{top_bear['शेअर (Symbol)']}** ({top_bear['मंदी % (Bearish)']}%)")

# संपूर्ण टेबल
st.subheader("📋 सर्व शेअर्सची रँकिंग")
st.dataframe(df_final, use_container_width=True)
