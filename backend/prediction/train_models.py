"""
Train 5 Gradient-Boosting price-prediction models (v2) and save artefacts.

Improvements over v1:
  - Uses ALL numeric columns (Avg/Min/Max Price per Sqft) as features
  - Target-encodes locality (smoothed mean price) instead of label encoding
  - Engineers extra features: estimated_price, price_range
  - Log-transforms the target (prices are right-skewed)
  - Removes outliers (BHK > 10, extreme prices)
  - Uses HistGradientBoostingRegressor (fast, handles NaN natively)

Usage (run from the backend/ directory):
    python -m prediction.train_models
"""

import os
import warnings

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, r2_score
from sklearn.model_selection import train_test_split

warnings.filterwarnings("ignore")

# ── paths ──────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ML_MODELS_DIR = os.path.join(BASE_DIR, "ml_models")
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "..", "scrapped_data")

os.makedirs(ML_MODELS_DIR, exist_ok=True)

# ── dataset definitions ────────────────────────────────────────────────────
DATASETS = {
    "apartment": {
        "file": "apartment_data_cleaned.xlsx",
        "locality_col": "Locality",
        "bhk_col": "BHK",
        "sqft_col": "Sqft (sqft)",
        "avg_price_sqft_col": "Avg Price/Sqft (₹)",
        "min_price_sqft_col": "Price Min/Sqft (₹)",
        "max_price_sqft_col": "Price Max/Sqft (₹)",
        "price_col": "Price (₹)",
        "has_bhk": True,
    },
    "villa": {
        "file": "villa_cleaned.xlsx",
        "locality_col": "Locality",
        "bhk_col": "BHK",
        "sqft_col": "Sqft (sqft)",
        "avg_price_sqft_col": "Avg Price/Sqft (₹)",
        "min_price_sqft_col": "Price Min/Sqft (₹)",
        "max_price_sqft_col": "Price Max/Sqft (₹)",
        "price_col": "Price (₹)",
        "has_bhk": True,
    },
    "independent_house": {
        "file": "independent_house_cleaned.xlsx",
        "locality_col": "Locality",
        "bhk_col": "BHK",
        "sqft_col": "Sqft (sqft)",
        "avg_price_sqft_col": "Avg Price/Sqft (₹)",
        "min_price_sqft_col": "Price Min/Sqft (₹)",
        "max_price_sqft_col": "Price Max/Sqft (₹)",
        "price_col": "Price (₹)",
        "has_bhk": True,
    },
    "plot": {
        "file": "plot_cleaned.xlsx",
        "locality_col": "Locality",
        "bhk_col": None,
        "sqft_col": "Plot Area (sqft)",
        "avg_price_sqft_col": "Avg Price/Sqft (₹)",
        "min_price_sqft_col": "Price Min/Sqft (₹)",
        "max_price_sqft_col": "Price Max/Sqft (₹)",
        "price_col": "Price (₹)",
        "has_bhk": False,
    },
    "backup": {
        "file": "main_backup_file.xlsx",
        "locality_col": "Locality",
        "bhk_col": "BHK",
        "sqft_col": "Sqft (sqft)",
        "avg_price_sqft_col": "Avg Price/Sqft (₹)",
        "min_price_sqft_col": "Price Min/Sqft (₹)",
        "max_price_sqft_col": "Price Max/Sqft (₹)",
        "price_col": "Price (₹)",
        "has_bhk": True,
    },
}


def _clean_numeric(series: pd.Series) -> pd.Series:
    """Coerce a column to float, turning non-numeric values to NaN."""
    return pd.to_numeric(series.astype(str).str.replace(",", ""), errors="coerce")


def _target_encode(series: pd.Series, target: pd.Series, smoothing: int = 30):
    """
    Smoothed target-encoding: blend the per-category mean with the global mean.
    Returns (encoded_series, mapping_dict, global_mean).
    """
    global_mean = target.mean()
    agg = target.groupby(series).agg(["mean", "count"])
    smooth = (agg["count"] * agg["mean"] + smoothing * global_mean) / (
        agg["count"] + smoothing
    )
    mapping = smooth.to_dict()
    encoded = series.map(mapping)
    return encoded, mapping, global_mean


def train_single_model(name: str, cfg: dict) -> None:
    path = os.path.join(DATA_DIR, cfg["file"])
    if not os.path.exists(path):
        print(f"[SKIP] {name}: file not found → {path}")
        return

    df = pd.read_excel(path)
    print(f"\n{'=' * 60}")
    print(f"Training: {name}  |  rows loaded: {len(df)}")

    # ── column refs ────────────────────────────────────────────────────────
    loc_col = cfg["locality_col"]
    sqft_col = cfg["sqft_col"]
    price_col = cfg["price_col"]
    avg_ps_col = cfg["avg_price_sqft_col"]
    min_ps_col = cfg["min_price_sqft_col"]
    max_ps_col = cfg["max_price_sqft_col"]

    # ── clean numerics ─────────────────────────────────────────────────────
    for c in [sqft_col, price_col, avg_ps_col, min_ps_col, max_ps_col]:
        df[c] = _clean_numeric(df[c])

    required = [loc_col, sqft_col, price_col, avg_ps_col, min_ps_col, max_ps_col]
    if cfg["has_bhk"]:
        df[cfg["bhk_col"]] = _clean_numeric(df[cfg["bhk_col"]])
        required.append(cfg["bhk_col"])

    df.dropna(subset=required, inplace=True)
    df = df[(df[sqft_col] > 0) & (df[price_col] > 0)]

    # ── outlier removal ────────────────────────────────────────────────────
    if cfg["has_bhk"]:
        df = df[df[cfg["bhk_col"]].between(1, 10)]
    # Remove extreme price outliers (beyond 1st/99th percentiles)
    low, high = df[price_col].quantile(0.01), df[price_col].quantile(0.99)
    df = df[df[price_col].between(low, high)]

    df[loc_col] = df[loc_col].astype(str).str.strip()
    print(f"  rows after cleaning: {len(df)}")

    if len(df) < 20:
        print(f"  [SKIP] not enough data to train.")
        return

    # ── target-encode locality ─────────────────────────────────────────────
    loc_encoded, loc_mapping, loc_global_mean = _target_encode(
        df[loc_col], df[price_col]
    )
    df["locality_te"] = loc_encoded

    # ── build locality stats lookup (for prediction time) ──────────────────
    locality_stats = (
        df.groupby(loc_col)
        .agg(
            avg_price_sqft=(avg_ps_col, "first"),
            min_price_sqft=(min_ps_col, "first"),
            max_price_sqft=(max_ps_col, "first"),
            min_sqft=(sqft_col, "min"),
            max_sqft=(sqft_col, "max"),
        )
        .to_dict("index")
    )

    # ── feature engineering ────────────────────────────────────────────────
    df["price_range_sqft"] = df[max_ps_col] - df[min_ps_col]
    df["estimated_price"] = df[sqft_col] * df[avg_ps_col]

    # ── assemble feature matrix ────────────────────────────────────────────
    feature_cols = [
        "locality_te",
        sqft_col,
        avg_ps_col,
        min_ps_col,
        max_ps_col,
        "price_range_sqft",
        "estimated_price",
    ]
    if cfg["has_bhk"]:
        feature_cols.insert(2, cfg["bhk_col"])

    X = df[feature_cols].values.astype(np.float64)
    y_raw = df[price_col].values.astype(np.float64)

    # ── log-transform target ───────────────────────────────────────────────
    y = np.log1p(y_raw)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    y_test_raw = np.expm1(y_test)

    # ── train HistGradientBoosting ─────────────────────────────────────────
    model = HistGradientBoostingRegressor(
        max_iter=600,
        max_depth=8,
        learning_rate=0.06,
        min_samples_leaf=10,
        l2_regularization=0.1,
        random_state=42,
    )
    model.fit(X_train, y_train)

    # ── evaluate (on original scale) ───────────────────────────────────────
    y_pred_log = model.predict(X_test)
    y_pred = np.expm1(y_pred_log)
    r2 = r2_score(y_test_raw, y_pred)
    mae = mean_absolute_error(y_test_raw, y_pred)
    mape = mean_absolute_percentage_error(y_test_raw, y_pred) * 100
    print(f"  R²   = {r2:.4f}")
    print(f"  MAE  = ₹{mae:,.0f}")
    print(f"  MAPE = {mape:.1f}%")

    # ── save artefacts ─────────────────────────────────────────────────────
    artefacts = {
        "model": model,
        "loc_target_map": loc_mapping,          # locality → target-encoded value
        "loc_global_mean": loc_global_mean,      # fallback for unseen localities
        "locality_stats": locality_stats,        # locality → {avg, min, max price/sqft}
        "median_stats": {                        # fallback stats for unseen localities
            "avg_price_sqft": float(df[avg_ps_col].median()),
            "min_price_sqft": float(df[min_ps_col].median()),
            "max_price_sqft": float(df[max_ps_col].median()),
            "min_sqft": float(df[sqft_col].quantile(0.05)),
            "max_sqft": float(df[sqft_col].quantile(0.95)),
        },
        "feature_cols": feature_cols,
        "has_bhk": cfg["has_bhk"],
    }
    joblib.dump(artefacts, os.path.join(ML_MODELS_DIR, f"{name}_model.pkl"))

    localities = sorted(df[loc_col].unique().tolist())
    joblib.dump(localities, os.path.join(ML_MODELS_DIR, f"{name}_localities.pkl"))

    print(f"  Saved: {name}_model.pkl, {name}_localities.pkl")
    print(f"  Known localities: {len(localities)}")
    print(f"  Features ({len(feature_cols)}): {feature_cols}")


def main():
    print("=" * 60)
    print("Price Prediction v2 — Model Training")
    print("=" * 60)

    for name, cfg in DATASETS.items():
        train_single_model(name, cfg)

    print(f"\n{'=' * 60}")
    print("All models trained.  Artefacts saved to:", ML_MODELS_DIR)
    print("=" * 60)


if __name__ == "__main__":
    main()
