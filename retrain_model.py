# retrain_model.py
# Retrains the house price model using final.xlsx + master_locality_data.csv
# Overwrites house_price_model.pkl, encoders.pkl, feature_columns.pkl
# Usage: python retrain_model.py  (run from project root)

import os
import pickle
import logging
import numpy as np
import pandas as pd

from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import r2_score, mean_squared_error

# --- Configuration ---

DATASET_PATH     = "scrapped data/final.xlsx"
MASTER_DATA_PATH = "ml_model/master_locality_data.csv"
MODEL_DIR        = "ml_model"

# New locality-level features to add from master_locality_data.csv
NEW_FEATURES = [
    "amenity_score",
    "connectivity_score",
    "crime_score",
    "growth_score",
    "metro_distance_km",
    "it_hub_distance_km",
]

# Categorical columns to label-encode
CATEGORICAL_COLS = ["Locality", "Property Type", "Furnishing"]

# Target column
TARGET_COL = "Price (INR)"


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    logging.info("Loading dataset from %s ...", DATASET_PATH)
    df = pd.read_excel(DATASET_PATH)
    logging.info("Loaded %d rows × %d cols", len(df), len(df.columns))

    logging.info("Loading master locality data from %s ...", MASTER_DATA_PATH)
    master = pd.read_csv(MASTER_DATA_PATH)
    logging.info("Master data: %d localities", len(master))

    return df, master


def clean_dataset(df: pd.DataFrame) -> pd.DataFrame:
    logging.info("Cleaning dataset ...")

    # Drop rows missing critical columns
    critical = ["Locality", "Price (INR)", "Area (SqFt)", "BHK", "Bathrooms", "Property Type"]
    before = len(df)
    df = df.dropna(subset=critical)
    logging.info("Dropped %d rows with missing critical values", before - len(df))

    # Ensure numeric types
    df["Area (SqFt)"]   = pd.to_numeric(df["Area (SqFt)"],   errors="coerce")
    df["BHK"]           = pd.to_numeric(df["BHK"],           errors="coerce")
    df["Bathrooms"]     = pd.to_numeric(df["Bathrooms"],      errors="coerce")
    df["Price (INR)"]   = pd.to_numeric(df["Price (INR)"],   errors="coerce")
    df = df.dropna(subset=["Area (SqFt)", "BHK", "Bathrooms", "Price (INR)"])

    # Convert price to Lakhs for model consistency
    df["Price_Lakhs"] = df["Price (INR)"] / 100_000

    # Remove extreme outliers (bottom 1% and top 1% of price)
    low  = df["Price_Lakhs"].quantile(0.01)
    high = df["Price_Lakhs"].quantile(0.99)
    before = len(df)
    df = df[(df["Price_Lakhs"] >= low) & (df["Price_Lakhs"] <= high)]
    logging.info("Removed %d outlier rows (price outside %.1f–%.1f L)", before - len(df), low, high)

    # Fill missing / empty Furnishing with a safe default
    if "Furnishing" in df.columns:
        # Treat empty / whitespace-only strings as NaN
        df["Furnishing"] = df["Furnishing"].replace(r'^\s*$', np.nan, regex=True)
        mode_vals = df["Furnishing"].dropna().mode()
        fill_val = mode_vals.iloc[0] if len(mode_vals) > 0 else "Unfurnished"
        df["Furnishing"] = df["Furnishing"].fillna(fill_val)
    else:
        df["Furnishing"] = "Unfurnished"

    # Strip whitespace from string columns (after filling NaN so astype(str) is safe)
    for col in ["Locality", "Property Type", "Furnishing"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    logging.info("Clean dataset: %d rows", len(df))
    return df


def merge_locality_features(df: pd.DataFrame, master: pd.DataFrame) -> pd.DataFrame:
    logging.info("Merging locality features ...")

    # Normalise locality names for matching (use consistent lowercase key)
    df["locality_lower"]     = df["Locality"].str.lower().str.strip()
    master["locality_lower"] = master["locality"].str.lower().str.strip()

    master_slim = master[["locality_lower"] + NEW_FEATURES].drop_duplicates("locality_lower")

    merged = df.merge(master_slim, on="locality_lower", how="left")

    # How many rows got matched
    matched = merged[NEW_FEATURES[0]].notna().sum()
    logging.info(
        "Matched %d / %d rows to locality features (%.1f%%)",
        matched, len(merged), 100 * matched / len(merged)
    )

    # Fill unmatched with column medians (safe fallback)
    for col in NEW_FEATURES:
        median_val = master[col].median()
        nulls = merged[col].isna().sum()
        if nulls > 0:
            logging.warning("Filling %d nulls in '%s' with median %.2f", nulls, col, median_val)
            merged[col] = merged[col].fillna(median_val)

    merged = merged.drop(columns=["locality_lower"])
    return merged


def encode_categoricals(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    logging.info("Encoding categorical columns ...")
    encoders = {}

    for col in CATEGORICAL_COLS:
        if col not in df.columns:
            logging.warning("Column '%s' not found — skipping encoder", col)
            continue
        le = LabelEncoder()
        df[f"{col}_enc"] = le.fit_transform(df[col].astype(str))
        encoders[col] = le
        logging.info("  Encoded '%s' → %d classes", col, len(le.classes_))

    return df, encoders


def build_feature_matrix(df: pd.DataFrame) -> tuple[pd.DataFrame, list]:
    feature_cols = [
        "Locality_enc",
        "Area (SqFt)",
        "BHK",
        "Bathrooms",
        "Property Type_enc",
        "Furnishing_enc",
    ] + NEW_FEATURES

    # Only keep columns that actually exist
    feature_cols = [c for c in feature_cols if c in df.columns]
    logging.info("Feature columns: %s", feature_cols)

    # Rename to match existing prediction_service.py expectations
    rename_map = {
        "Area (SqFt)": "Area_SqFt",
        "BHK":         "BHK_num",
    }
    df = df.rename(columns=rename_map)
    feature_cols = [rename_map.get(c, c) for c in feature_cols]

    return df, feature_cols


def train_model(X_train, y_train):
    logging.info("Training GradientBoostingRegressor ...")
    model = GradientBoostingRegressor(
        n_estimators=300,
        learning_rate=0.05,
        max_depth=5,
        min_samples_split=5,
        subsample=0.8,
        random_state=42,
    )
    model.fit(X_train, y_train)
    return model


def evaluate(model, X_train, X_test, y_train, y_test, label=""):
    train_pred = model.predict(X_train)
    test_pred  = model.predict(X_test)

    train_r2   = r2_score(y_train, train_pred)
    test_r2    = r2_score(y_test,  test_pred)
    train_rmse = np.sqrt(mean_squared_error(y_train, train_pred))
    test_rmse  = np.sqrt(mean_squared_error(y_test,  test_pred))

    print(f"\n{'-'*40}")
    print(f"  {label}")
    print(f"  Train R2:   {train_r2:.4f}   RMSE: {train_rmse:.2f} L")
    print(f"  Test  R2:   {test_r2:.4f}   RMSE: {test_rmse:.2f} L")
    print(f"{'-'*40}")

    return test_r2, test_rmse


def save_artifacts(model, encoders: dict, feature_cols: list):
    logging.info("Saving model artifacts to %s ...", MODEL_DIR)
    os.makedirs(MODEL_DIR, exist_ok=True)

    with open(os.path.join(MODEL_DIR, "house_price_model.pkl"), "wb") as f:
        pickle.dump(model, f)

    with open(os.path.join(MODEL_DIR, "encoders.pkl"), "wb") as f:
        pickle.dump(encoders, f)

    with open(os.path.join(MODEL_DIR, "feature_columns.pkl"), "wb") as f:
        pickle.dump(feature_cols, f)

    logging.info("Saved: house_price_model.pkl, encoders.pkl, feature_columns.pkl")


def main():
    setup_logging()
    logging.info("=== Starting model retraining ===")

    # 1. Load data
    df, master = load_data()

    # 2. Clean
    df = clean_dataset(df)

    # 3. Merge new locality features
    df = merge_locality_features(df, master)

    # 4. Encode categoricals
    df, encoders = encode_categoricals(df)

    # 5. Build feature matrix
    df, feature_cols = build_feature_matrix(df)

    # 6. Train/test split
    X = df[feature_cols]
    y = df["Price_Lakhs"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    logging.info("Train: %d rows | Test: %d rows", len(X_train), len(X_test))

    # 7. Load OLD model for before/after comparison (best-effort)
    old_model_path = os.path.join(MODEL_DIR, "house_price_model.pkl")
    old_feature_path = os.path.join(MODEL_DIR, "feature_columns.pkl")
    if os.path.isfile(old_model_path) and os.path.isfile(old_feature_path):
        try:
            with open(old_model_path, "rb") as f:
                old_model = pickle.load(f)
            with open(old_feature_path, "rb") as f:
                old_features = pickle.load(f)
            # Old model needs ALL its original features; skip if they don't match
            if set(old_features).issubset(X_test.columns):
                evaluate(old_model, X_train[old_features], X_test[old_features],
                         y_train, y_test, "BEFORE retraining (old model)")
            else:
                logging.warning("Old model features don't match current data — skipping comparison")
        except Exception as e:
            logging.warning("Could not evaluate old model: %s", e)

    # 8. Train new model
    model = train_model(X_train, y_train)

    # 9. Evaluate new model
    evaluate(model, X_train, X_test, y_train, y_test, "AFTER retraining (new model)")

    # 10. Feature importance
    print("\n=== Top 10 Feature Importances ===")
    importances = sorted(
        zip(feature_cols, model.feature_importances_),
        key=lambda x: x[1], reverse=True
    )
    for feat, imp in importances[:10]:
        bar = "#" * int(imp * 50)
        print(f"  {feat:35s} {imp:.4f} {bar}")

    # 11. Save
    save_artifacts(model, encoders, feature_cols)

    print("\nRetraining complete! Restart Django server to load the new model.")


if __name__ == "__main__":
    main()