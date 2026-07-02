"""
train_model.py
Trains a "Buy Now vs Wait" classifier.

Problem framing
----------------
For every (product, store, day) in the history, we look 14 days into the future.
If the lowest price in that window drops at least 3% below today's price, the
correct label is WAIT (a better deal is coming). Otherwise it's BUY_NOW.

Features (all computable from price history up to "today", i.e. no lookahead leak
except in the label itself, which is only used for training):
  - price_vs_7d_ma     : current price vs 7-day moving average
  - price_vs_30d_ma     : current price vs 30-day moving average
  - price_vs_hist_min   : how far above the historical minimum we are
  - price_vs_hist_max   : how far below the historical maximum we are
  - volatility_14d      : rolling std dev / mean, recent volatility
  - days_since_low      : days since the lowest price seen so far
  - trend_slope_14d     : linear trend of last 14 days (rising/falling)
  - day_of_week         : weekly seasonality signal

Model: RandomForestClassifier (handles nonlinear interactions well, robust to
scale differences between features, and gives interpretable feature importances
-- useful to talk through in an interview).
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score, roc_auc_score
import joblib

LOOKAHEAD_DAYS = 14
DROP_THRESHOLD = 0.03  # 3% future drop => WAIT


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["product_id", "store", "date"]).reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])

    out = []
    for (pid, store), g in df.groupby(["product_id", "store"]):
        g = g.sort_values("date").reset_index(drop=True)
        price = g["price"]

        g["ma7"] = price.rolling(7, min_periods=1).mean()
        g["ma30"] = price.rolling(30, min_periods=1).mean()
        g["hist_min"] = price.expanding().min()
        g["hist_max"] = price.expanding().max()
        g["roll_std14"] = price.rolling(14, min_periods=2).std().fillna(0)

        g["price_vs_7d_ma"] = (price - g["ma7"]) / g["ma7"]
        g["price_vs_30d_ma"] = (price - g["ma30"]) / g["ma30"]
        g["price_vs_hist_min"] = (price - g["hist_min"]) / g["hist_min"]
        g["price_vs_hist_max"] = (price - g["hist_max"]) / g["hist_max"]
        g["volatility_14d"] = g["roll_std14"] / g["ma7"]

        # days since the running historical minimum
        running_min_idx = price.expanding().apply(lambda x: x.values.argmin(), raw=False)
        g["days_since_low"] = g.index - running_min_idx

        # 14-day trend slope via simple linear fit on the last 14 points
        def slope(window):
            if len(window) < 2:
                return 0.0
            x = np.arange(len(window))
            return np.polyfit(x, window, 1)[0]

        g["trend_slope_14d"] = price.rolling(14, min_periods=2).apply(slope, raw=True).fillna(0)
        g["trend_slope_14d_norm"] = g["trend_slope_14d"] / g["ma7"]

        g["day_of_week"] = g["date"].dt.dayofweek

        # label: look ahead LOOKAHEAD_DAYS, did price drop >= DROP_THRESHOLD?
        future_min = price.shift(-1).rolling(LOOKAHEAD_DAYS, min_periods=1).min().shift(-(LOOKAHEAD_DAYS - 1))
        g["future_min"] = future_min
        g["label"] = ((g["future_min"] - price) / price <= -DROP_THRESHOLD).astype(int)  # 1 = WAIT

        g["product_id"] = pid
        g["store"] = store
        out.append(g)

    result = pd.concat(out, ignore_index=True)
    # drop tail rows where we don't have a full lookahead window to label
    result = result.dropna(subset=["future_min"])
    return result


FEATURE_COLS = [
    "price_vs_7d_ma", "price_vs_30d_ma", "price_vs_hist_min", "price_vs_hist_max",
    "volatility_14d", "days_since_low", "trend_slope_14d_norm", "day_of_week",
]


def main():
    history = pd.read_csv("data/price_history.csv")
    feat_df = build_features(history)

    X = feat_df[FEATURE_COLS]
    y = feat_df["label"]

    print(f"Training rows: {len(X)}  |  WAIT ratio: {y.mean():.2%}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    clf = RandomForestClassifier(
        n_estimators=300, max_depth=6, min_samples_leaf=20,
        class_weight="balanced", random_state=42, n_jobs=-1,
    )
    clf.fit(X_train, y_train)

    preds = clf.predict(X_test)
    proba = clf.predict_proba(X_test)[:, 1]

    print("\nAccuracy:", round(accuracy_score(y_test, preds), 4))
    print("ROC AUC :", round(roc_auc_score(y_test, proba), 4))
    print("\nClassification report:")
    print(classification_report(y_test, preds, target_names=["BUY_NOW", "WAIT"]))

    importances = pd.Series(clf.feature_importances_, index=FEATURE_COLS).sort_values(ascending=False)
    print("Feature importances:")
    print(importances.to_string())

    joblib.dump({"model": clf, "features": FEATURE_COLS}, "ml/model.pkl")
    print("\nSaved model -> ml/model.pkl")


if __name__ == "__main__":
    main()
