# PricePilot — Smart Price Comparison Platform (AI-Powered)

Compares product prices across multiple online stores and uses a machine
learning model to recommend **Buy Now** or **Wait** based on historical
pricing patterns.

## Features

- **Price comparison** across 5 simulated stores, 39 products, 6 categories.
- **AI Buy Now / Wait recommendation** per product, from a RandomForest model trained on 120 days of price history.
- **Watchlist with price-drop alerts** — track any product at a target price. Stored server-side in SQLite, keyed to an anonymous session cookie (no login required for the demo). Optionally add an email; if `SMTP_HOST`/`SMTP_USER`/`SMTP_PASS` env vars are set, a real email is sent when the target is hit — otherwise the alert is logged to the console so the code path is still verifiable without setting up your own mail credentials.

## Why this project

This started as a resume line ("AI-powered price comparison") and became a
full, working project: a synthetic-but-realistic pricing dataset, a trained
scikit-learn classifier, a Flask REST API, and a frontend that visualizes
price history and the model's recommendation for each product.

## Architecture

```
price-comparison-ai/
├── data/
│   └── generate_data.py     # builds products.csv + price_history.csv (120 days, 5 stores, 39 products)
├── ml/
│   ├── train_model.py        # feature engineering + RandomForest training
│   └── model.pkl              # trained model (generated)
├── backend/
│   ├── app.py                 # Flask REST API + page routes
│   ├── model_utils.py         # loads model, computes live features, returns recommendation
│   ├── watchlist.py            # SQLite persistence + email alert logic for the watchlist feature
│   ├── templates/index.html
│   └── static/{css,js}
├── requirements.txt
└── README.md
```

**Flow:** `generate_data.py` → `train_model.py` → `app.py` loads `model.pkl`
and the CSVs into memory and serves both the API and the web page.

## The ML problem

**Task:** given a product's price history up to today, predict whether the
price will drop **≥3% within the next 14 days** (label = `WAIT`) or not
(label = `BUY_NOW`).

**Features** (all derived from price history, no future leakage):
- price vs 7-day / 30-day moving average
- price vs all-time historical min / max
- 14-day rolling volatility
- days since the lowest price seen so far
- 14-day price trend slope
- day of week

**Model:** `RandomForestClassifier` (scikit-learn), chosen for handling
nonlinear feature interactions and giving interpretable feature importances.

**Results on held-out test data:**
- Accuracy: ~0.70
- ROC AUC: ~0.77
- Most predictive features: price vs 30-day average, price vs historical max

These aren't inflated numbers — they're realistic for a price-prediction
problem with genuine noise, which is a better story in an interview than a
suspicious 99% accuracy.

## Run it locally

```bash
cd price-comparison-ai
pip install -r requirements.txt

python data/generate_data.py      # generates the dataset
python ml/train_model.py          # trains the model, prints metrics, saves ml/model.pkl

cd backend
python app.py                      # serves http://127.0.0.1:5050
```

Open `http://127.0.0.1:5050` in your browser. Search or filter products,
click a card to see the store-by-store price comparison, 60-day price
history chart, and the model's Buy Now / Wait recommendation with its
reasoning.

## API endpoints

| Endpoint | Description |
|---|---|
| `GET /api/categories` | list of product categories |
| `GET /api/products?search=&category=` | product list with best price/store |
| `GET /api/products/<id>` | prices per store + 60-day history |
| `GET /api/products/<id>/recommendation?store=` | BUY_NOW/WAIT + confidence + reason |
| `GET /api/watchlist` | current session's tracked products |
| `POST /api/watchlist` | add `{product_id, target_price, email}` to watchlist |
| `DELETE /api/watchlist/<id>` | remove a tracked item |
| `POST /api/watchlist/check-alerts` | scan for price drops, fire alerts, mark as notified |

## Talking points for interviews

- End-to-end ownership: data generation → feature engineering → model
  training/evaluation → API → frontend.
- Deliberately framed this as a classification problem (not regression) with
  a business-meaningful threshold (3% drop within 14 days), because "will
  the price change" is less useful to a shopper than "should I buy today."
- Reported both accuracy and ROC AUC, and discussed feature importances,
  rather than just a single headline metric.
- Frontend consumes the model through a clean REST boundary — the ML
  service could be swapped or redeployed independently of the UI.

## Deploying live (Render.com, free tier)

1. Push this project to a GitHub repo.
2. On [render.com](https://render.com), create a **New Web Service** and connect the repo.
3. Root directory: leave blank (project root).
4. Build command:
   ```
   pip install -r requirements.txt && python data/generate_data.py && python ml/train_model.py
   ```
5. Start command:
   ```
   cd backend && gunicorn app:app
   ```
6. Deploy. Render gives you a live URL like `https://pricepilot-xxxx.onrender.com` — that's what goes on your resume and LinkedIn.

Note: Render's free tier sleeps after inactivity, so the first load after idle time can take ~30-50 seconds to spin back up. That's normal, not a bug.

## Next steps (good to mention as future work)

- Replace synthetic data with a real product-price API or scraped dataset.
- Retrain periodically as new price data arrives (currently a static batch model).
- Add user accounts + price-drop email/SMS alerts.
- Track model performance over time (drift monitoring).
