"""
app.py
Flask API + server for the Smart Price Comparison Platform.

Endpoints
---------
GET /api/categories
GET /api/products?search=&category=
GET /api/products/<product_id>
GET /api/products/<product_id>/recommendation?store=<store>   (store optional -> uses cheapest store)
"""
import os
import pandas as pd
from flask import Flask, jsonify, request, render_template

from model_utils import recommend

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "..", "data")

app = Flask(__name__)

products_df = pd.read_csv(os.path.join(DATA_DIR, "products.csv"))
history_df = pd.read_csv(os.path.join(DATA_DIR, "price_history.csv"))
history_df["date"] = pd.to_datetime(history_df["date"])


def latest_prices() -> pd.DataFrame:
    """Latest price per product per store."""
    idx = history_df.groupby(["product_id", "store"])["date"].idxmax()
    return history_df.loc[idx]


def best_price_per_product(latest: pd.DataFrame) -> pd.DataFrame:
    best_idx = latest.groupby("product_id")["price"].idxmin()
    return latest.loc[best_idx][["product_id", "store", "price"]].rename(
        columns={"store": "best_store", "price": "best_price"}
    )


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/categories")
def categories():
    cats = sorted(products_df["category"].unique().tolist())
    return jsonify(cats)


@app.route("/api/products")
def list_products():
    search = request.args.get("search", "").strip().lower()
    category = request.args.get("category", "").strip()

    df = products_df.copy()
    if search:
        df = df[df["name"].str.lower().str.contains(search)]
    if category and category.lower() != "all":
        df = df[df["category"] == category]

    latest = latest_prices()
    best = best_price_per_product(latest)
    merged = df.merge(best, on="product_id", how="left")

    results = merged.to_dict(orient="records")
    return jsonify(results)


@app.route("/api/products/<int:product_id>")
def product_detail(product_id: int):
    product = products_df[products_df["product_id"] == product_id]
    if product.empty:
        return jsonify({"error": "not found"}), 404
    product = product.iloc[0].to_dict()

    hist = history_df[history_df["product_id"] == product_id].sort_values("date")
    hist_60 = hist[hist["date"] >= hist["date"].max() - pd.Timedelta(days=60)]

    series_by_store = {}
    latest_by_store = {}
    for store, g in hist_60.groupby("store"):
        g = g.sort_values("date")
        series_by_store[store] = [
            {"date": d.strftime("%Y-%m-%d"), "price": round(p, 2)}
            for d, p in zip(g["date"], g["price"])
        ]
        latest_by_store[store] = round(g["price"].iloc[-1], 2)

    cheapest_store = min(latest_by_store, key=latest_by_store.get)

    return jsonify({
        "product": product,
        "prices": latest_by_store,
        "cheapest_store": cheapest_store,
        "history": series_by_store,
    })


@app.route("/api/products/<int:product_id>/recommendation")
def product_recommendation(product_id: int):
    store = request.args.get("store")

    hist = history_df[history_df["product_id"] == product_id].sort_values("date")
    if hist.empty:
        return jsonify({"error": "not found"}), 404

    if not store:
        latest = hist[hist["date"] == hist["date"].max()]
        store = latest.loc[latest["price"].idxmin(), "store"]

    store_hist = hist[hist["store"] == store].sort_values("date")
    if store_hist.empty:
        return jsonify({"error": "no history for store"}), 404

    result = recommend(store_hist["price"])
    result["store"] = store
    result["current_price"] = round(float(store_hist["price"].iloc[-1]), 2)
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(debug=False, host="0.0.0.0", port=port)
