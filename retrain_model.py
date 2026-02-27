# retrain_model.py
# Retrains the house price model using final_enriched.xlsx + master_locality_data.csv
# Overwrites house_price_model.pkl, encoders.pkl, feature_columns.pkl
# Usage: python retrain_model.py  (run from project root)

import os
import pickle
import logging
import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import r2_score, mean_squared_error

# --- Configuration ---

DATASET_PATH     = "scrapped data/final_augmented.xlsx"
MASTER_DATA_PATH = "ml_model/master_locality_data.csv"
MODEL_DIR        = "ml_model"

# Locality-level features from master_locality_data.csv
LOCALITY_GEO_FEATURES = [
    "amenity_score",
    "connectivity_score",
    "crime_score",
    "growth_score",
    "metro_distance_km",
    "it_hub_distance_km",
]

# Engineered interaction features (computed at training + prediction time)
ENGINEERED_FEATURES = [
    "BHK_x_Area",
    "Bath_x_Area",
    "BHK_x_Bath",
    "Area_squared",
    "locality_median_pps",
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
    logging.info("Loaded %d rows x %d cols", len(df), len(df.columns))

    logging.info("Loading master locality data from %s ...", MASTER_DATA_PATH)
    master = pd.read_csv(MASTER_DATA_PATH)
    logging.info("Master data: %d localities", len(master))

    return df, master


def clean_dataset(df: pd.DataFrame) -> pd.DataFrame:
    logging.info("Cleaning dataset ...")

    # Drop rows missing critical columns
    critical = ["Locality", "Price (INR)", "Area (SqFt)", "BHK", "Property Type"]
    before = len(df)
    df = df.dropna(subset=critical)
    logging.info("Dropped %d rows with missing critical values", before - len(df))

    # Ensure numeric types
    df["Area (SqFt)"] = pd.to_numeric(df["Area (SqFt)"], errors="coerce")
    df["BHK"]          = pd.to_numeric(df["BHK"],          errors="coerce")
    df["Bathrooms"]    = pd.to_numeric(df["Bathrooms"],    errors="coerce")
    df["Price (INR)"]  = pd.to_numeric(df["Price (INR)"],  errors="coerce")
    df = df.dropna(subset=["Area (SqFt)", "BHK", "Price (INR)"])

    # Fill missing bathrooms with BHK (reasonable proxy)
    df["Bathrooms"] = df["Bathrooms"].fillna(df["BHK"])

    # --- Strict range filters ---
    before = len(df)
    df = df[df["Price (INR)"] >= 2_000_000]       # min 20 Lakhs
    df = df[df["Price (INR)"] <= 500_000_000]      # max 50 Crore
    df = df[df["Area (SqFt)"] >= 300]              # min 300 sqft
    df = df[df["Area (SqFt)"] <= 15_000]           # max 15000 sqft
    df = df[df["BHK"].between(1, 6)]               # 1-6 BHK only
    logging.info("Removed %d rows outside valid ranges", before - len(df))

    # Convert price to Lakhs for model consistency
    df["Price_Lakhs"] = df["Price (INR)"] / 100_000

    # Remove extreme outliers (bottom 1% and top 1% of price)
    low  = df["Price_Lakhs"].quantile(0.01)
    high = df["Price_Lakhs"].quantile(0.99)
    before = len(df)
    df = df[(df["Price_Lakhs"] >= low) & (df["Price_Lakhs"] <= high)]
    logging.info("Removed %d outlier rows (price outside %.1f-%.1f L)", before - len(df), low, high)

    # Fill missing / empty Furnishing with a safe default
    if "Furnishing" in df.columns:
        df["Furnishing"] = df["Furnishing"].replace(r'^\s*$', np.nan, regex=True)
        mode_vals = df["Furnishing"].dropna().mode()
        fill_val = mode_vals.iloc[0] if len(mode_vals) > 0 else "Unfurnished"
        df["Furnishing"] = df["Furnishing"].fillna(fill_val)
    else:
        df["Furnishing"] = "Unfurnished"

    # Strip whitespace from string columns
    for col in ["Locality", "Property Type", "Furnishing"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    logging.info("Clean dataset: %d rows", len(df))
    return df


def merge_locality_features(df: pd.DataFrame, master: pd.DataFrame) -> pd.DataFrame:
    logging.info("Merging locality features ...")

    df["locality_lower"]     = df["Locality"].str.lower().str.strip()
    master["locality_lower"] = master["locality"].str.lower().str.strip()

    master_slim = master[["locality_lower"] + LOCALITY_GEO_FEATURES].drop_duplicates("locality_lower")
    merged = df.merge(master_slim, on="locality_lower", how="left")

    matched = merged[LOCALITY_GEO_FEATURES[0]].notna().sum()
    logging.info(
        "Matched %d / %d rows to locality features (%.1f%%)",
        matched, len(merged), 100 * matched / len(merged)
    )

    for col in LOCALITY_GEO_FEATURES:
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
            logging.warning("Column '%s' not found -- skipping encoder", col)
            continue
        le = LabelEncoder()
        df[f"{col}_enc"] = le.fit_transform(df[col].astype(str))
        encoders[col] = le
        logging.info("  Encoded '%s' -> %d classes", col, len(le.classes_))

    return df, encoders


def engineer_features(df: pd.DataFrame, train_idx: pd.Index) -> tuple[pd.DataFrame, dict]:
    """Create interaction features and locality median price/sqft.

    locality_median_pps is computed from TRAINING rows only to avoid data leakage.
    Returns the modified df and the locality_pps lookup dict for saving.
    """
    logging.info("Engineering interaction features ...")

    # Derive Price/SqFt (used only for computing locality median, NOT as a direct feature)
    df["_Price_SqFt"] = df["Price_Lakhs"] / df["Area_SqFt"]

    # Interaction features (these use only input features, no leakage)
    df["BHK_x_Area"]   = df["BHK"] * df["Area_SqFt"]
    df["Bath_x_Area"]  = df["Bathrooms"] * df["Area_SqFt"]
    df["BHK_x_Bath"]   = df["BHK"] * df["Bathrooms"]
    df["Area_squared"]  = df["Area_SqFt"] ** 2

    # Locality median price-per-sqft: compute from training data only
    train = df.loc[train_idx]
    locality_medians = train.groupby("Locality")["_Price_SqFt"].median()
    global_median = train["_Price_SqFt"].median()

    locality_pps_lookup = locality_medians.to_dict()
    locality_pps_lookup["__global_median__"] = global_median

    df["locality_median_pps"] = df["Locality"].map(locality_medians).fillna(global_median)

    logging.info(
        "  locality_median_pps: %d localities, global median %.4f L/sqft",
        len(locality_medians), global_median,
    )
    logging.info(
        "  Interaction features: BHK_x_Area, Bath_x_Area, BHK_x_Bath, Area_squared"
    )

    # Drop temporary column
    df = df.drop(columns=["_Price_SqFt"])

    return df, locality_pps_lookup


def build_feature_matrix(df: pd.DataFrame) -> tuple[pd.DataFrame, list]:
    feature_cols = [
        "Locality_enc",
        "Area_SqFt",
        "BHK",
        "Bathrooms",
        "Property Type_enc",
        "Furnishing_enc",
    ] + ENGINEERED_FEATURES + LOCALITY_GEO_FEATURES

    # Only keep columns that actually exist
    feature_cols = [c for c in feature_cols if c in df.columns]
    logging.info("Feature columns (%d): %s", len(feature_cols), feature_cols)

    # Rename to match prediction_service.py expectations
    rename_map = {"BHK": "BHK_num"}
    df = df.rename(columns=rename_map)
    feature_cols = [rename_map.get(c, c) for c in feature_cols]

    return df, feature_cols


def train_model(X_train, y_train):
    logging.info("Training RandomForestRegressor ...")
    model = RandomForestRegressor(
        n_estimators=500,
        max_depth=15,
        min_samples_leaf=2,
        max_features='sqrt',
        n_jobs=-1,
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

    print(f"\n{'-'*50}")
    print(f"  {label}")
    print(f"  Train R2:   {train_r2:.4f}   RMSE: {train_rmse:.2f} L")
    print(f"  Test  R2:   {test_r2:.4f}   RMSE: {test_rmse:.2f} L")
    print(f"{'-'*50}")

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


def save_locality_pps(lookup: dict):
    path = os.path.join(MODEL_DIR, "locality_pps.pkl")
    with open(path, "wb") as f:
        pickle.dump(lookup, f)
    logging.info("Saved locality_pps.pkl (%d entries)", len(lookup))


def main():
    setup_logging()
    logging.info("=== Starting model retraining ===")

    # 1. Load data
    df, master = load_data()

    # 2. Clean
    df = clean_dataset(df)

    # 3. Merge locality geo-features
    df = merge_locality_features(df, master)

    # 4. Encode categoricals
    df, encoders = encode_categoricals(df)

    # 5. Rename Area column early (needed for feature engineering)
    df = df.rename(columns={"Area (SqFt)": "Area_SqFt"})

    # 6. Train/test split (BEFORE engineering locality_median_pps to avoid leakage)
    y = df["Price_Lakhs"]
    train_idx, test_idx = train_test_split(
        df.index, test_size=0.2, random_state=42
    )
    logging.info("Train: %d rows | Test: %d rows", len(train_idx), len(test_idx))

    # 7. Engineer interaction features + locality_median_pps
    df, locality_pps_lookup = engineer_features(df, train_idx)

    # 8. Build feature matrix
    df, feature_cols = build_feature_matrix(df)

    X_train = df.loc[train_idx, feature_cols]
    X_test  = df.loc[test_idx, feature_cols]
    y_train = y.loc[train_idx]
    y_test  = y.loc[test_idx]

    # 9. Load OLD model for before/after comparison (best-effort)
    old_model_path = os.path.join(MODEL_DIR, "house_price_model.pkl")
    old_feature_path = os.path.join(MODEL_DIR, "feature_columns.pkl")
    if os.path.isfile(old_model_path) and os.path.isfile(old_feature_path):
        try:
            with open(old_model_path, "rb") as f:
                old_model = pickle.load(f)
            with open(old_feature_path, "rb") as f:
                old_features = pickle.load(f)
            if set(old_features).issubset(X_test.columns):
                evaluate(old_model, X_train[old_features], X_test[old_features],
                         y_train, y_test, "BEFORE retraining (old model)")
            else:
                logging.warning("Old model features don't match current data -- skipping comparison")
        except Exception as e:
            logging.warning("Could not evaluate old model: %s", e)

    # 10. Train new model
    model = train_model(X_train, y_train)

    # 11. Evaluate new model
    evaluate(model, X_train, X_test, y_train, y_test, "AFTER retraining (new model)")

    # 12. Feature importance
    print("\n=== Top 15 Feature Importances ===")
    importances = sorted(
        zip(feature_cols, model.feature_importances_),
        key=lambda x: x[1], reverse=True
    )
    for feat, imp in importances[:15]:
        bar = "#" * int(imp * 50)
        print(f"  {feat:35s} {imp:.4f} {bar}")

    # 13. Save
    save_artifacts(model, encoders, feature_cols)
    save_locality_pps(locality_pps_lookup)

    # 14. Sensitivity sanity-check -- every prediction MUST be different
    print("\n=== Sensitivity sanity-check ===")
    global_med_pps = locality_pps_lookup["__global_median__"]

    test_cases = [
        ("Gachibowli",    2, 2, 1000),  # baseline
        ("Gachibowli",    2, 2, 1200),  # area changed
        ("Gachibowli",    2, 3, 1000),  # bathrooms changed
        ("Gachibowli",    3, 2, 1000),  # BHK changed
        ("Banjara Hills", 2, 2, 1000),  # locality changed
        ("Shamirpet",     2, 2, 1000),  # locality changed
    ]
    predictions = []
    for locality, bhk, baths, area in test_cases:
        loc_pps = locality_pps_lookup.get(locality, global_med_pps)
        sample = {
            "Locality_enc":      encoders["Locality"].transform([locality])[0]
                                 if locality in encoders["Locality"].classes_ else 0,
            "Area_SqFt":         float(area),
            "BHK_num":           bhk,
            "Bathrooms":         baths,
            "Property Type_enc": encoders["Property Type"].transform(["Apartment"])[0]
                                 if "Apartment" in encoders["Property Type"].classes_ else 0,
            "Furnishing_enc":    encoders["Furnishing"].transform(["Semi-Furnished"])[0]
                                 if "Semi-Furnished" in encoders["Furnishing"].classes_ else 0,
            "BHK_x_Area":        bhk * area,
            "Bath_x_Area":       baths * area,
            "BHK_x_Bath":        bhk * baths,
            "Area_squared":      area ** 2,
            "locality_median_pps": loc_pps,
        }
        # Add locality geo-features
        loc_lower = locality.lower().strip()
        master_row = master[master["locality"].str.lower().str.strip() == loc_lower]
        for feat in LOCALITY_GEO_FEATURES:
            if not master_row.empty:
                sample[feat] = float(master_row.iloc[0][feat])
            else:
                sample[feat] = float(master[feat].median())

        row_df = pd.DataFrame([sample])[feature_cols]
        pred = model.predict(row_df)[0]
        predictions.append(pred)
        print(f"  {locality:20s} {bhk}BHK {baths}bath {area}sqft -> {pred:8.1f} L ({pred/100:.2f} Cr)")

    # Check all predictions are unique
    unique_count = len(set(round(p, 1) for p in predictions))
    total_count = len(predictions)
    if unique_count == total_count:
        print(f"\n  PASS: All {total_count} predictions are different!")
    else:
        print(f"\n  WARNING: Only {unique_count}/{total_count} unique predictions -- model may lack sensitivity")

    print("\nRetraining complete! Restart Django server to load the new model.")


if __name__ == "__main__":
    main()