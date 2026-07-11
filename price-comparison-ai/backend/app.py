"""
app.py
Flask API + server for the Smart Price Comparison Platform.

Endpoints
---------
GET  /api/categories
GET  /api/products?search=&category=&sort=       (sort: price_asc|price_desc|rating|discount)
GET  /api/products/<product_id>
GET  /api/products/<product_id>/recommendation?store=<store>   (store optional -> uses cheapest store)
GET  /api/products/compare?ids=1001,1002,1003
GET  /api/watchlist
POST /api/watchlist                 { product_id, target_price, email }
DELETE /api/watchlist/<item_id>
POST /api/watchlist/check-alerts    triggers a scan for price drops -> target hit
"""
import os
import uuid
import pandas as pd
from flask import Flask, jsonify, request, render_template, session

from model_utils import recommend
import watchlist as wl

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "..", "data")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")

wl.init_db()

products_df = pd.read_csv(os.path.join(DATA_DIR, "products.csv"))
history_df = pd.read_csv(os.path.join(DATA_DIR, "price_history.csv"))
history_df["date"] = pd.to_datetime(history_df["date"])


def get_session_id() -> str:
    if "sid" not in session:
        session["sid"] = str(uuid.uuid4())
    return session["sid"]


def current_price_for(product_id: int) -> tuple[float, str]:
    """Cheapest current price + store for a product."""
    hist = history_df[history_df["product_id"] == product_id]
    latest = hist[hist["date"] == hist["date"].max()]
    row = latest.loc[latest["price"].idxmin()]
    return float(row["price"]), str(row["store"])


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
    sort = request.args.get("sort", "").strip()

    df = products_df.copy()
    if search:
        df = df[df["name"].str.lower().str.contains(search)]
    if category and category.lower() != "all":
        df = df[df["category"] == category]

    latest = latest_prices()
    best = best_price_per_product(latest)
    merged = df.merge(best, on="product_id", how="left")
    merged["discount_pct"] = ((merged["mrp"] - merged["best_price"]) / merged["mrp"] * 100).round(0)

    if sort == "price_asc":
        merged = merged.sort_values("best_price")
    elif sort == "price_desc":
        merged = merged.sort_values("best_price", ascending=False)
    elif sort == "rating":
        merged = merged.sort_values("rating", ascending=False)
    elif sort == "discount":
        merged = merged.sort_values("discount_pct", ascending=False)

    results = merged.to_dict(orient="records")
    return jsonify(results)


@app.route("/api/products/compare")
def compare_products():
    ids = request.args.get("ids", "")
    product_ids = [int(x) for x in ids.split(",") if x.strip().isdigit()]
    if not product_ids:
        return jsonify({"error": "no product ids given"}), 400

    latest = latest_prices()
    out = []
    for pid in product_ids:
        prod = products_df[products_df["product_id"] == pid]
        if prod.empty:
            continue
        prod = prod.iloc[0].to_dict()
        prod_prices = latest[latest["product_id"] == pid]
        prices_by_store = {row["store"]: round(row["price"], 2) for _, row in prod_prices.iterrows()}
        cheapest_store = min(prices_by_store, key=prices_by_store.get)
        store_hist = history_df[(history_df["product_id"] == pid) & (history_df["store"] == cheapest_store)].sort_values("date")
        rec = recommend(store_hist["price"])
        out.append({
            **prod,
            "prices": prices_by_store,
            "cheapest_store": cheapest_store,
            "cheapest_price": prices_by_store[cheapest_store],
            "recommendation": rec["recommendation"],
            "confidence": rec["confidence"],
        })
    return jsonify(out)


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


@app.route("/api/watchlist", methods=["GET"])
def get_watchlist():
    sid = get_session_id()
    items = wl.list_items(sid)

    enriched = []
    for item in items:
        prod = products_df[products_df["product_id"] == item["product_id"]]
        if prod.empty:
            continue
        prod = prod.iloc[0]
        price, store = current_price_for(item["product_id"])
        enriched.append({
            **item,
            "name": prod["name"],
            "category": prod["category"],
            "current_price": round(price, 2),
            "current_store": store,
            "target_hit": price <= item["target_price"],
        })
    return jsonify(enriched)


@app.route("/api/watchlist", methods=["POST"])
def add_watchlist():
    sid = get_session_id()
    data = request.get_json(force=True)
    product_id = int(data.get("product_id"))
    target_price = float(data.get("target_price"))
    email = (data.get("email") or "").strip() or None

    if products_df[products_df["product_id"] == product_id].empty:
        return jsonify({"error": "product not found"}), 404

    wl.add_item(sid, product_id, target_price, email)
    return jsonify({"status": "added"}), 201


@app.route("/api/watchlist/<int:item_id>", methods=["DELETE"])
def delete_watchlist(item_id: int):
    sid = get_session_id()
    wl.remove_item(sid, item_id)
    return jsonify({"status": "removed"})


@app.route("/api/watchlist/check-alerts", methods=["POST"])
def check_alerts():
    """Scans all un-notified watchlist rows and fires alerts for any that hit their target.
    In a production system this would run on a schedule (e.g. Render Cron Job); here it's
    exposed as an endpoint so it can be triggered on demand from the UI for the demo."""
    triggered = []
    for item in wl.all_unnotified_items():
        price, store = current_price_for(item["product_id"])
        if price <= item["target_price"]:
            prod = products_df[products_df["product_id"] == item["product_id"]]
            name = prod.iloc[0]["name"] if not prod.empty else f"Product {item['product_id']}"
            sent = False
            if item["email"]:
                sent = wl.send_alert_email(item["email"], name, price, item["target_price"])
            wl.mark_notified(item["id"])
            triggered.append({
                "product_id": item["product_id"], "name": name,
                "current_price": round(price, 2), "target_price": item["target_price"],
                "store": store, "email_sent": sent,
            })
    return jsonify({"checked": True, "triggered": triggered})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(debug=False, host="0.0.0.0", port=port)
