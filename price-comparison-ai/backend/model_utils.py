"""
model_utils.py
Turns a raw price history (for one product at one store) into the same feature
vector used at training time, and returns a human-readable recommendation.

Keeping this logic separate from the Flask routes means the ML side of the
project can be explained, tested, and demoed independently of the web layer.
"""
import numpy as np
import pandas as pd
import joblib
import os

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "ml", "model.pkl")

_bundle = joblib.load(MODEL_PATH)
MODEL = _bundle["model"]
FEATURE_COLS = _bundle["features"]


def compute_features_for_today(price_series: pd.Series) -> dict:
    """price_series: chronologically sorted prices (most recent last)."""
    price_series = price_series.reset_index(drop=True)
    price = price_series.iloc[-1]

    ma7 = price_series.tail(7).mean()
    ma30 = price_series.tail(30).mean()
    hist_min = price_series.min()
    hist_max = price_series.max()
    roll_std14 = price_series.tail(14).std()
    roll_std14 = 0.0 if pd.isna(roll_std14) else roll_std14

    days_since_low = len(price_series) - 1 - int(price_series.values.argmin())

    tail14 = price_series.tail(14).values
    if len(tail14) >= 2:
        slope = np.polyfit(np.arange(len(tail14)), tail14, 1)[0]
    else:
        slope = 0.0

    features = {
        "price_vs_7d_ma": (price - ma7) / ma7,
        "price_vs_30d_ma": (price - ma30) / ma30,
        "price_vs_hist_min": (price - hist_min) / hist_min,
        "price_vs_hist_max": (price - hist_max) / hist_max,
        "volatility_14d": roll_std14 / ma7,
        "days_since_low": days_since_low,
        "trend_slope_14d_norm": slope / ma7,
        "day_of_week": 0,  # not known for "today" relative to demo data; neutral weekday
    }
    return features


def recommend(price_series: pd.Series) -> dict:
    feats = compute_features_for_today(price_series)
    X = pd.DataFrame([feats])[FEATURE_COLS]
    proba_wait = MODEL.predict_proba(X)[0, 1]
    label = "WAIT" if proba_wait >= 0.5 else "BUY_NOW"

    # Build a short human-readable reason from the strongest signals
    reasons = []
    if feats["price_vs_hist_min"] < 0.03:
        reasons.append("price is near its all-time low")
    if feats["price_vs_30d_ma"] < -0.03:
        reasons.append("well below its 30-day average")
    if feats["trend_slope_14d_norm"] < -0.01:
        reasons.append("trending downward over the last 2 weeks")
    if feats["price_vs_hist_max"] > -0.03:
        reasons.append("close to its recent peak price")
    if feats["trend_slope_14d_norm"] > 0.01 and label == "WAIT":
        reasons.append("volatile pricing suggests a dip may follow")
    if not reasons:
        reasons.append("price has been stable relative to recent history")

    return {
        "recommendation": label,
        "confidence": round(float(proba_wait if label == "WAIT" else 1 - proba_wait), 3),
        "wait_probability": round(float(proba_wait), 3),
        "reason": "Because " + " and ".join(reasons[:2]) + ".",
    }
