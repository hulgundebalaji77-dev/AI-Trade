import numpy as np
import pandas as pd
from scipy.stats import norm

class FOProbabilityEngine:
    def __init__(self, risk_free_rate=0.065):
        self.r = risk_free_rate

    def black_scholes_prob(self, spot, iv, dte):
        """१. ऑप्शन व्होलॅटिलिटीवर आधारित गणिती संभाव्यता"""
        T = max(dte, 1) / 365.0
        if iv <= 0:
            return 50.0, 50.0, 0.0, spot, spot
        
        expected_move = spot * iv * np.sqrt(T)
        upper_band = spot + expected_move
        lower_band = spot - expected_move
        
        # d2 calculation (Risk-neutral probability of expiring in-the-money)
        d2 = ((self.r - 0.5 * (iv ** 2)) * T) / (iv * np.sqrt(T))
        p_up = float(norm.cdf(d2) * 100)
        p_down = 100.0 - p_up
        return p_up, p_down, expected_move, lower_band, upper_band

    def pcr_score(self, pcr):
        """२. पुट-कॉल रेशो (PCR) स्कोअर (० ते १००)"""
        # PCR 0.5 (अति मंदी) ते 1.5 (अति तेजी) नॉर्मलाइझेशन
        score = ((pcr - 0.5) / (1.5 - 0.5)) * 100
        return float(np.clip(score, 0, 100))

    def buildup_score(self, price_chg, oi_chg):
        """३. किंमत आणि ओपन इंटरेस्ट बिल्डअप स्कोअर"""
        if price_chg > 0 and oi_chg > 0:
            return 85.0, "Long Buildup"         # ताकदीची तेजी
        elif price_chg > 0 and oi_chg <= 0:
            return 65.0, "Short Covering"       # मध्यम तेजी
        elif price_chg <= 0 and oi_chg <= 0:
            return 40.0, "Long Unwinding"       # मध्यम मंदी
        else:
            return 15.0, "Short Buildup"        # ताकदीची मंदी

    def max_pain_drift(self, spot, max_pain):
        """४. मॅक्स पेन पातळीच्या दिशेने खेचला जाणारा कल"""
        diff_pct = ((max_pain - spot) / spot) * 100
        # मॅक्स पेन वर असल्यास भाव वाढण्याची शक्यता जास्त
        drift_score = 50.0 + (diff_pct * 5)
        return float(np.clip(drift_score, 10, 90))

    def evaluate_universe(self, stocks_data, dte=15):
        results = []
        for s in stocks_data:
            # १. ब्लॅक शोल्स संभाव्यता
            bs_up, bs_down, exp_move, l_range, u_range = self.black_scholes_prob(
                s["spot"], s["iv"], dte
            )
            
            # २. पीसीआर स्कोअर
            pcr_sc = self.pcr_score(s["pcr"])
            
            # ३. एफ अँड ओ बिल्डअप स्कोअर
            buildup_sc, regime = self.buildup_score(s["price_chg"], s["oi_chg"])
            
            # ४. मॅक्स पेन स्कोअर
            mp_sc = self.max_pain_drift(s["spot"], s["max_pain"])
            
            # एकत्रित वेटेड संभाव्यता (Weighted Ensemble Model)
            # Weights: Buildup(35%), PCR(25%), Black-Scholes(20%), Max Pain(20%)
            bullish_prob = (
                (buildup_sc * 0.35) + 
                (pcr_sc * 0.25) + 
                (bs_up * 0.20) + 
                (mp_sc * 0.20)
            )
            bearish_prob = 100.0 - bullish_prob
            
            # अंतिम निष्कर्ष (Action Signal)
            if bullish_prob >= 70:
                signal = "STRONG BULLISH (खरेदी कल)"
            elif bullish_prob >= 55:
                signal = "MILD BULLISH (सावध तेजी)"
            elif bullish_prob <= 30:
                signal = "STRONG BEARISH (विक्री कल)"
            elif bullish_prob <= 45:
                signal = "MILD BEARISH (सावध मंदी)"
            else:
                signal = "NEUTRAL (रेंजबाउंड)"

            results.append({
                "Symbol": s["symbol"],
                "Spot": round(s["spot"], 1),
                "Bullish Prob (%)": round(bullish_prob, 1),
                "Bearish Prob (%)": round(bearish_prob, 1),
                "Signal": signal,
                "Regime": regime,
                "Expected Range": f"{int(l_range)} - {int(u_range)}",
                "PCR": s["pcr"],
                "Max Pain": s["max_pain"]
            })

        # सर्वाधिक तेजी ते सर्वाधिक मंदीनुसार क्रमवारी (Ranking)
        df = pd.DataFrame(results).sort_values(by="Bullish Prob (%)", ascending=False)
        return df

# --- वापर आणि चाचणी डेटा ---
if __name__ == "__main__":
    fo_market_data = [
        {"symbol": "RELIANCE",   "spot": 2980.0, "iv": 0.21, "price_chg": 1.5,  "oi_chg": 6.2,  "pcr": 1.35, "max_pain": 3020},
        {"symbol": "TCS",        "spot": 3950.0, "iv": 0.18, "price_chg": -1.2, "oi_chg": 4.5,  "pcr": 0.65, "max_pain": 3900},
        {"symbol": "HDFCBANK",   "spot": 1640.0, "iv": 0.19, "price_chg": 0.8,  "oi_chg": -1.5, "pcr": 1.05, "max_pain": 1650},
        {"symbol": "INFY",       "spot": 1820.0, "iv": 0.24, "price_chg": -1.8, "oi_chg": -3.2, "pcr": 0.72, "max_pain": 1800},
        {"symbol": "SBIN",       "spot": 810.0,  "iv": 0.26, "price_chg": 2.2,  "oi_chg": 8.1,  "pcr": 1.40, "max_pain": 830},
        {"symbol": "TATAMOTORS", "spot": 925.0,  "iv": 0.28, "price_chg": -2.4, "oi_chg": 9.5,  "pcr": 0.52, "max_pain": 900}
    ]

    engine = FOProbabilityEngine()
    model_output = engine.evaluate_universe(fo_market_data, dte=14)
    print(model_output.to_string(index=False))
