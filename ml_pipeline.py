"""
Hyderabad Real Estate - ML Price Prediction Pipeline
=====================================================
Steps:
  1. Explore the data
  2. Clean & preprocess
  3. Train & compare models (Random Forest, XGBoost, Gradient Boosting)
  4. Save best model + encoders
  5. Sample prediction
"""

import sys, os, re, warnings, pickle
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

warnings.filterwarnings("ignore")

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(PROJECT_DIR, "scrapped data", "final.xlsx")
MODEL_DIR = os.path.join(PROJECT_DIR, "ml_model")

# ============================================================
# STEP 1 - Explore the data
# ============================================================
print("=" * 60)
print("STEP 1 - Data Exploration")
print("=" * 60)

try:
    df = pd.read_csv(DATA_PATH.replace(".xlsx", ".csv"))
    print("Loaded CSV file.")
except Exception:
    df = pd.read_excel(DATA_PATH)
    print("Loaded Excel file.")

print(f"\nShape: {df.shape}")
print(f"\nColumns:\n  {list(df.columns)}")
print(f"\nNull counts:\n{df.isnull().sum()}")
print(f"\nSample rows:\n{df.head(5).to_string()}")

# ============================================================
# STEP 2 - Clean & Preprocess
# ============================================================
print("\n" + "=" * 60)
print("STEP 2 - Cleaning & Preprocessing")
print("=" * 60)

# --- 2a. Drop rows where Price (INR) is missing or "N/A" ---
df = df[df["Price (INR)"].notna()]
df = df[df["Price (INR)"].astype(str).str.strip().str.upper() != "N/A"]
print(f"After dropping missing/N/A prices: {df.shape[0]} rows")

# --- 2b. Parse Price (INR) -> numeric lakhs ---
def parse_price_lakhs(val):
    """Convert price value to lakhs (float).
    Handles:
      - Raw numeric strings like '43099999.99'  -> divide by 100,000
      - '45 Lac' / '45 Lakh'                    -> 45.0
      - '1.2 Cr' / '1.2 Crore'                  -> 120.0
      - Already numeric values                   -> divide by 100,000
    """
    if pd.isna(val):
        return np.nan
    s = str(val).strip()

    # Check for Cr / Crore
    m = re.search(r"([\d,.]+)\s*(?:Cr|Crore)", s, re.IGNORECASE)
    if m:
        return float(m.group(1).replace(",", "")) * 100.0

    # Check for Lac / Lakh
    m = re.search(r"([\d,.]+)\s*(?:Lac|Lakh)", s, re.IGNORECASE)
    if m:
        return float(m.group(1).replace(",", ""))

    # Otherwise treat as raw number -> convert to lakhs
    try:
        num = float(re.sub(r"[^\d.]", "", s))
        if num > 100_000:
            return num / 100_000  # raw rupees -> lakhs
        return num
    except ValueError:
        return np.nan

df["Price_Lakhs"] = df["Price (INR)"].apply(parse_price_lakhs)
df = df.dropna(subset=["Price_Lakhs"])
print(f"After parsing price: {df.shape[0]} rows  |  Price range: {df['Price_Lakhs'].min():.1f} - {df['Price_Lakhs'].max():.1f} Lakhs")

# --- 2c. Parse Area (SqFt) -> numeric float ---
def parse_area(val):
    if pd.isna(val):
        return np.nan
    s = str(val).replace(",", "").strip()
    m = re.search(r"[\d.]+", s)
    return float(m.group()) if m else np.nan

df["Area_SqFt"] = df["Area (SqFt)"].apply(parse_area)
df = df.dropna(subset=["Area_SqFt"])

# --- 2d. Parse BHK -> int ---
def parse_bhk(val):
    if pd.isna(val):
        return np.nan
    m = re.search(r"(\d+)", str(val))
    return int(m.group(1)) if m else np.nan

df["BHK_num"] = df["BHK"].apply(parse_bhk)
df = df.dropna(subset=["BHK_num"])
df["BHK_num"] = df["BHK_num"].astype(int)

# --- 2e. Remove outliers using IQR on Price_Lakhs ---
Q1 = df["Price_Lakhs"].quantile(0.01)
Q3 = df["Price_Lakhs"].quantile(0.99)
before_outlier = len(df)
df = df[(df["Price_Lakhs"] >= Q1) & (df["Price_Lakhs"] <= Q3)]
print(f"Removed {before_outlier - len(df)} outlier rows (1st-99th percentile filter)")
print(f"Price range after outlier removal: {df['Price_Lakhs'].min():.1f} - {df['Price_Lakhs'].max():.1f} Lakhs")

# Also remove unrealistic areas
df = df[(df["Area_SqFt"] >= 100) & (df["Area_SqFt"] <= 20000)]

# --- 2f. Encode categoricals ---
encoders = {}
for col in ["Locality", "Property Type", "Furnishing"]:
    le = LabelEncoder()
    # Fill NaN with "Unknown" before encoding
    df[col] = df[col].fillna("Unknown").astype(str)
    df[col + "_enc"] = le.fit_transform(df[col])
    encoders[col] = le

# --- 2g. Drop irrelevant / sparse columns ---
drop_cols = ["City", "Project Name", "Source", "Scraped At",
             "Price (INR)", "Area (SqFt)", "Price/SqFt", "BHK",
             "Locality", "Property Type", "Furnishing"]
df.drop(columns=[c for c in drop_cols if c in df.columns], inplace=True)

print(f"\nFinal dataset: {df.shape}")
print(f"Columns: {list(df.columns)}")
print(df.head(3).to_string())
print(f"\nPrice stats:\n{df['Price_Lakhs'].describe()}")

# ============================================================
# STEP 3 - Train & Compare Models
# ============================================================
print("\n" + "=" * 60)
print("STEP 3 - Model Training & Comparison")
print("=" * 60)

FEATURES = ["Locality_enc", "Area_SqFt", "BHK_num", "Bathrooms",
            "Property Type_enc", "Furnishing_enc"]
TARGET = "Price_Lakhs"

X = df[FEATURES]
y = df[TARGET]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)
print(f"Train size: {X_train.shape[0]}  |  Test size: {X_test.shape[0]}")

models = {
    "Random Forest": RandomForestRegressor(
        n_estimators=300, max_depth=15, min_samples_split=5,
        min_samples_leaf=2, random_state=42, n_jobs=-1
    ),
    "XGBoost": XGBRegressor(
        n_estimators=500, learning_rate=0.05, max_depth=8,
        subsample=0.8, colsample_bytree=0.8,
        random_state=42, verbosity=0
    ),
    "Gradient Boosting": GradientBoostingRegressor(
        n_estimators=500, learning_rate=0.05, max_depth=6,
        subsample=0.8, min_samples_split=5,
        random_state=42
    ),
}

results = {}
for name, model in models.items():
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    rmse = np.sqrt(mean_squared_error(y_test, preds))
    r2 = r2_score(y_test, preds)
    results[name] = {"model": model, "MAE": mae, "RMSE": rmse, "R2": r2}
    print(f"\n  {name}:")
    print(f"    MAE  = {mae:.2f} Lakhs")
    print(f"    RMSE = {rmse:.2f} Lakhs")
    print(f"    R2   = {r2:.4f}")

best_name = max(results, key=lambda k: results[k]["R2"])
best_model = results[best_name]["model"]
best_r2 = results[best_name]["R2"]
print(f"\n>>> Best model: {best_name}  (R2 = {best_r2:.4f})")

# ============================================================
# STEP 4 - Save Model & Encoders
# ============================================================
print("\n" + "=" * 60)
print("STEP 4 - Saving Model Artifacts")
print("=" * 60)

os.makedirs(MODEL_DIR, exist_ok=True)

model_path = os.path.join(MODEL_DIR, "house_price_model.pkl")
enc_path = os.path.join(MODEL_DIR, "encoders.pkl")
feat_path = os.path.join(MODEL_DIR, "feature_columns.pkl")

with open(model_path, "wb") as f:
    pickle.dump(best_model, f)
print(f"  [OK] Model saved   -> {model_path}")

with open(enc_path, "wb") as f:
    pickle.dump(encoders, f)
print(f"  [OK] Encoders saved -> {enc_path}")

with open(feat_path, "wb") as f:
    pickle.dump(FEATURES, f)
print(f"  [OK] Features saved -> {feat_path}")

# ============================================================
# STEP 5 - Sample Prediction
# ============================================================
print("\n" + "=" * 60)
print("STEP 5 - Sample Prediction")
print("=" * 60)

sample_input = {
    "Locality": "Gachibowli",
    "Area_SqFt": 1200.0,
    "BHK_num": 2,
    "Bathrooms": 2,
    "Property Type": "Apartment",
    "Furnishing": "Semi-Furnished",
}

# Encode categorical values using saved encoders
def safe_encode(encoder, value):
    """Encode a value; if unseen, return the most-common class index."""
    if value in encoder.classes_:
        return encoder.transform([value])[0]
    else:
        print(f"    [!] '{value}' not seen during training - using fallback encoding")
        return 0  # fallback

sample_encoded = {
    "Locality_enc": safe_encode(encoders["Locality"], sample_input["Locality"]),
    "Area_SqFt": sample_input["Area_SqFt"],
    "BHK_num": sample_input["BHK_num"],
    "Bathrooms": sample_input["Bathrooms"],
    "Property Type_enc": safe_encode(encoders["Property Type"], sample_input["Property Type"]),
    "Furnishing_enc": safe_encode(encoders["Furnishing"], sample_input["Furnishing"]),
}

sample_df = pd.DataFrame([sample_encoded])[FEATURES]
predicted_price = best_model.predict(sample_df)[0]

print(f"\n  Input:")
for k, v in sample_input.items():
    print(f"    {k}: {v}")
print(f"\n  Predicted Price: {predicted_price:.2f} Lakhs")
if predicted_price >= 100:
    print(f"     (= Rs {predicted_price / 100:.2f} Crore)")
else:
    print(f"     (= Rs {predicted_price:.2f} Lakh)")

print("\n" + "=" * 60)
print(f"DONE - Best Model: {best_name} | R2 = {best_r2:.4f}")
print(f"   Model saved at: {model_path}")
print(f"   Ready for API integration!")
print("=" * 60)
