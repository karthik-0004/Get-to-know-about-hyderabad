"""
Train 4 rental prediction models using HistGradientBoostingRegressor.

Models:
  - rent_1bhk  (rent_1bhk_clean.xlsx)
  - rent_2bhk  (rent_2bhk_clean.xlsx)
  - rent_3bhk  (rent_3bhk_clean.xlsx)
  - rent_backup (renter_clean.xlsx — all BHK, used as fallback)

Usage (run from the backend/ directory):
    python -m prediction.train_rental_models
"""

import os
import warnings

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OrdinalEncoder

warnings.filterwarnings("ignore")

# ── paths ──────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ML_MODELS_DIR = os.path.join(BASE_DIR, "ml_models")
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "..", "scrapped_data")

os.makedirs(ML_MODELS_DIR, exist_ok=True)

# ── dataset definitions ────────────────────────────────────────────────────
DATASETS = {
    "rent_1bhk": "rent_1bhk_clean.xlsx",
    "rent_2bhk": "rent_2bhk_clean.xlsx",
    "rent_3bhk": "rent_3bhk_clean.xlsx",
    "rent_backup": "renter_clean.xlsx",
}

# Column names (verified from the xlsx files)
LOCALITY_COL = "Locality"
BHK_COL = "BHK"
SQFT_COL = "Sqft"
FURNISHING_COL = "Furnishing"
PROPERTY_TYPE_COL = "Property Type"
TARGET_COL = "Monthly Rent"
AVG_RENT_COL = "Avg Rent"
MIN_RENT_COL = "Min Rent"
MAX_RENT_COL = "Max Rent"


def train_single_model(name: str, filename: str) -> None:
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        print(f"[SKIP] {name}: file not found → {path}")
        return

    df = pd.read_excel(path)
    print(f"\n{'=' * 60}")
    print(f"Training: {name}  |  rows loaded: {len(df)}")
    print(f"Columns: {list(df.columns)}")

    # ── clean ──────────────────────────────────────────────────────────────
    df = df.dropna(subset=[TARGET_COL, SQFT_COL, LOCALITY_COL])
    df = df[df[TARGET_COL] > 0]
    df = df[df[SQFT_COL] > 0]

    # Strip whitespace from string columns
    for col in [LOCALITY_COL, FURNISHING_COL, PROPERTY_TYPE_COL]:
        df[col] = df[col].astype(str).str.strip()

    print(f"  rows after cleaning: {len(df)}")
    print(f"  Furnishing values: {sorted(df[FURNISHING_COL].unique())}")
    print(f"  Property Type values: {sorted(df[PROPERTY_TYPE_COL].unique())}")

    if len(df) < 20:
        print(f"  [SKIP] not enough data to train.")
        return

    # ── OrdinalEncoder for categorical columns ─────────────────────────────
    cat_cols = [LOCALITY_COL, FURNISHING_COL, PROPERTY_TYPE_COL]
    encoder = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
    df[cat_cols] = encoder.fit_transform(df[cat_cols])

    # ── feature matrix ─────────────────────────────────────────────────────
    # Include aggregate rent stats per locality (Avg/Min/Max Rent) for better accuracy
    is_backup = (name == "rent_backup")
    feature_cols = [LOCALITY_COL, SQFT_COL, FURNISHING_COL, PROPERTY_TYPE_COL,
                    AVG_RENT_COL, MIN_RENT_COL, MAX_RENT_COL]
    if is_backup:
        feature_cols.insert(2, BHK_COL)

    X = df[feature_cols].values.astype(np.float64)
    y = df[TARGET_COL].values.astype(np.float64)

    # ── train/test split ───────────────────────────────────────────────────
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # ── train HistGradientBoosting ─────────────────────────────────────────
    model = HistGradientBoostingRegressor(
        max_iter=500,
        max_depth=8,
        learning_rate=0.05,
        min_samples_leaf=20,
        random_state=42,
    )
    model.fit(X_train, y_train)

    # ── evaluate ───────────────────────────────────────────────────────────
    y_pred = model.predict(X_test)
    r2 = r2_score(y_test, y_pred)
    mae = mean_absolute_error(y_test, y_pred)
    print(f"  R²  = {r2:.4f}")
    print(f"  MAE = ₹{mae:,.0f}")

    # ── save artefacts ─────────────────────────────────────────────────────
    joblib.dump(model, os.path.join(ML_MODELS_DIR, f"{name}_model.pkl"))
    joblib.dump(encoder, os.path.join(ML_MODELS_DIR, f"{name}_encoder.pkl"))

    # Save known localities (from original string values before encoding)
    df_raw = pd.read_excel(path)
    df_raw[LOCALITY_COL] = df_raw[LOCALITY_COL].astype(str).str.strip()
    localities = sorted(df_raw[LOCALITY_COL].unique().tolist())
    joblib.dump(localities, os.path.join(ML_MODELS_DIR, f"{name}_localities.pkl"))

    # Save per-locality rent stats for prediction-time feature building
    locality_stats = (
        df_raw.groupby(LOCALITY_COL)
        .agg(
            avg_rent=(AVG_RENT_COL, "first"),
            min_rent=(MIN_RENT_COL, "first"),
            max_rent=(MAX_RENT_COL, "first"),
        )
        .to_dict("index")
    )
    median_stats = {
        "avg_rent": float(df_raw[AVG_RENT_COL].median()),
        "min_rent": float(df_raw[MIN_RENT_COL].median()),
        "max_rent": float(df_raw[MAX_RENT_COL].median()),
    }
    joblib.dump(
        {"locality_stats": locality_stats, "median_stats": median_stats,
         "has_bhk": (name == "rent_backup")},
        os.path.join(ML_MODELS_DIR, f"{name}_meta.pkl"),
    )

    print(f"  Saved: {name}_model/encoder/localities/meta.pkl")
    print(f"  Known localities: {len(localities)}")


def main():
    print("=" * 60)
    print("Rental Prediction — Model Training")
    print("=" * 60)

    for name, filename in DATASETS.items():
        train_single_model(name, filename)

    print(f"\n{'=' * 60}")
    print("All rental models trained.  Artefacts saved to:", ML_MODELS_DIR)
    print("=" * 60)


if __name__ == "__main__":
    main()
