"""
generate_data.py
Generates a realistic synthetic dataset for the Smart Price Comparison Platform:
  - products.csv        : catalog of products
  - price_history.csv   : daily price per product per store, 120 days

The synthetic data is built to *behave* like real e-commerce pricing:
  - a slow baseline trend (prices drift up/down over the quarter)
  - weekly seasonality (small dips on weekends, sale bumps)
  - randomized "flash sale" events per store
  - store-specific pricing offsets (some stores run consistently cheaper)
  - gaussian noise

This gives the ML model genuine signal to learn from instead of pure noise.
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

RNG = np.random.default_rng(42)

STORES = ["Amazon", "Flipkart", "Croma", "Reliance Digital"]
STORE_OFFSET = {"Amazon": 0.0, "Flipkart": -0.015, "Croma": 0.03, "Reliance Digital": 0.015}

CATEGORIES = {
    "Electronics": [
        ("Noise Cancelling Headphones X200", 5999),
        ("Smart Watch Series 5", 8999),
        ("Wireless Earbuds Pro", 3499),
        ("27-inch 4K Monitor", 22999),
        ("Mechanical Keyboard RGB", 4499),
        ("Portable SSD 1TB", 6999),
        ("Bluetooth Speaker Mini", 1999),
        ("Gaming Mouse Elite", 2499),
    ],
    "Mobiles": [
        ("Galaxy Nova 12", 34999),
        ("Pixel Lite 9", 27999),
        ("iPhone Aura 14", 69999),
        ("OnePlus Zen 11", 31999),
    ],
    "Home Appliances": [
        ("Robot Vacuum Cleaner", 15999),
        ("Air Fryer 5L", 5499),
        ("Microwave Oven 25L", 8499),
        ("Inverter AC 1.5 Ton", 32999),
        ("Water Purifier RO+UV", 11999),
    ],
    "Fashion": [
        ("Running Shoes Aerofit", 2999),
        ("Leather Backpack Urban", 1899),
        ("Smart Fitness Band", 1499),
        ("Denim Jacket Classic", 2299),
    ],
}

DAYS = 120
START_DATE = datetime.today() - timedelta(days=DAYS)


def make_price_series(base_price: float, n_days: int) -> np.ndarray:
    """One store's daily price series for one product."""
    t = np.arange(n_days)

    # slow baseline drift: random walk with mild mean reversion
    drift = np.cumsum(RNG.normal(0, base_price * 0.0025, n_days))
    drift -= np.linspace(0, drift[-1], n_days)  # detrend so it doesn't wander unboundedly
    seasonal_drift = base_price * 0.06 * np.sin(t / 18.0 + RNG.uniform(0, 6.28))

    # weekly seasonality: weekend micro-dips
    dow = (np.arange(n_days) % 7)
    weekend_dip = np.where((dow == 5) | (dow == 6), -base_price * 0.01, 0.0)

    # flash sale events: short sharp discounts, ~1 every 20 days
    flash = np.zeros(n_days)
    n_events = max(1, n_days // 22)
    event_days = RNG.choice(n_days, size=n_events, replace=False)
    for d in event_days:
        depth = RNG.uniform(0.08, 0.22) * base_price
        width = RNG.integers(2, 5)
        for w in range(width):
            if d + w < n_days:
                flash[d + w] -= depth * (1 - w / width)

    noise = RNG.normal(0, base_price * 0.006, n_days)

    price = base_price + drift + seasonal_drift + weekend_dip + flash + noise
    price = np.clip(price, base_price * 0.55, base_price * 1.25)
    return np.round(price, 2)


def main():
    products = []
    history_rows = []
    pid = 1000

    for category, items in CATEGORIES.items():
        for name, base_price in items:
            pid += 1
            products.append({
                "product_id": pid,
                "name": name,
                "category": category,
                "base_price": base_price,
            })

            for store in STORES:
                store_base = base_price * (1 + STORE_OFFSET[store] + RNG.uniform(-0.01, 0.01))
                series = make_price_series(store_base, DAYS)
                for i, price in enumerate(series):
                    date = (START_DATE + timedelta(days=int(i))).strftime("%Y-%m-%d")
                    history_rows.append({
                        "product_id": pid,
                        "store": store,
                        "date": date,
                        "price": float(price),
                    })

    products_df = pd.DataFrame(products)
    history_df = pd.DataFrame(history_rows)

    products_df.to_csv("data/products.csv", index=False)
    history_df.to_csv("data/price_history.csv", index=False)

    print(f"Generated {len(products_df)} products across {len(CATEGORIES)} categories.")
    print(f"Generated {len(history_df)} price points across {len(STORES)} stores over {DAYS} days.")


if __name__ == "__main__":
    main()
