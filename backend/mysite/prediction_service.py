"""
Prediction service — loads the trained ML model and encoders once at import
time and exposes a predict_price() function for the API layer.

New: also loads master_locality_data.csv to look up locality-level features
(amenity_score, connectivity_score, crime_score, growth_score,
metro_distance_km, it_hub_distance_km) at prediction time.
"""

import pickle
import logging

import pandas as pd
from django.conf import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load model artifacts once at module import (not per-request)
# ---------------------------------------------------------------------------
_model_dir = settings.ML_MODEL_DIR

with open(_model_dir / "house_price_model.pkl", "rb") as f:
    _model = pickle.load(f)

with open(_model_dir / "encoders.pkl", "rb") as f:
    _encoders = pickle.load(f)  # dict: {"Locality": LabelEncoder, ...}

with open(_model_dir / "feature_columns.pkl", "rb") as f:
    _feature_columns = pickle.load(f)  # list of column names

logger.info("ML model and encoders loaded from %s", _model_dir)

# ---------------------------------------------------------------------------
# Load master locality data for new feature lookup
# ---------------------------------------------------------------------------
_LOCALITY_FEATURES = [
    "amenity_score",
    "connectivity_score",
    "crime_score",
    "growth_score",
    "metro_distance_km",
    "it_hub_distance_km",
]

_master_df: pd.DataFrame | None = None

try:
    _master_path = _model_dir / "master_locality_data.csv"
    _master_df = pd.read_csv(_master_path)
    _master_df["locality_lower"] = _master_df["locality"].str.lower().str.strip()
    logger.info(
        "Loaded master locality data: %d localities from %s",
        len(_master_df), _master_path,
    )
except Exception as exc:
    logger.warning("Could not load master_locality_data.csv: %s — locality features will use medians", exc)
# ---------------------------------------------------------------------------
# Load locality median price-per-sqft lookup (trained feature)
# ---------------------------------------------------------------------------
_locality_pps: dict = {}
_global_median_pps: float = 0.05  # safe fallback

try:
    with open(_model_dir / "locality_pps.pkl", "rb") as f:
        _locality_pps = pickle.load(f)
    _global_median_pps = _locality_pps.pop("__global_median__", 0.05)
    logger.info(
        "Loaded locality_pps.pkl: %d localities, global median %.4f",
        len(_locality_pps), _global_median_pps,
    )
except Exception as exc:
    logger.warning("Could not load locality_pps.pkl: %s", exc)

def _get_locality_features(locality: str) -> dict:
    """Look up locality-level features from master_locality_data.csv.
    Falls back to median values if locality not found.
    """
    defaults = {col: 5.0 for col in _LOCALITY_FEATURES}
    defaults["metro_distance_km"] = 10.0
    defaults["it_hub_distance_km"] = 10.0

    if _master_df is None:
        return defaults

    key = locality.lower().strip()
    match = _master_df[_master_df["locality_lower"] == key]

    if match.empty:
        # Try partial match
        partial = _master_df[_master_df["locality_lower"].str.contains(key, na=False)]
        if not partial.empty:
            match = partial.iloc[[0]]

    if match.empty:
        logger.warning("Locality '%s' not found in master data — using defaults", locality)
        return defaults

    row = match.iloc[0]
    return {col: float(row[col]) if col in row and pd.notna(row[col]) else defaults[col]
            for col in _LOCALITY_FEATURES}


# ---------------------------------------------------------------------------
# Encoder helper
# ---------------------------------------------------------------------------
def _safe_encode(encoder_key: str, value: str) -> int:
    """Encode a categorical value using the saved LabelEncoder.

    If the label was never seen during training, fall back to the
    most-frequent class (index 0) instead of crashing.
    """
    if encoder_key not in _encoders:
        return 0
    encoder = _encoders[encoder_key]
    if value in encoder.classes_:
        return int(encoder.transform([value])[0])
    logger.warning(
        "Unseen label '%s' for encoder '%s' -- using fallback (index 0)",
        value,
        encoder_key,
    )
    return 0


# ---------------------------------------------------------------------------
# Public prediction function
# ---------------------------------------------------------------------------
def predict_price(
    locality: str,
    area_sqft: float,
    bhk: int,
    bathrooms: int,
    property_type: str,
    furnishing: str,
) -> dict:
    """Return a prediction dict with price in Lakhs and Crore."""

    area  = float(area_sqft)
    baths = int(bathrooms)
    bhk_i = int(bhk)

    # Base features
    sample = {
        "Locality_enc":       _safe_encode("Locality", locality),
        "Area_SqFt":          area,
        "BHK_num":            bhk_i,
        "Bathrooms":          baths,
        "Property Type_enc":  _safe_encode("Property Type", property_type),
        "Furnishing_enc":     _safe_encode("Furnishing", furnishing),
    }

    # Engineered interaction features (must match retrain_model.py)
    sample["BHK_x_Area"]           = bhk_i * area
    sample["Bath_x_Area"]          = baths * area
    sample["BHK_x_Bath"]           = bhk_i * baths
    sample["Area_squared"]         = area ** 2
    sample["locality_median_pps"]  = _locality_pps.get(
        locality, _global_median_pps
    )

    # New locality-level geo features
    locality_feats = _get_locality_features(locality)
    sample.update(locality_feats)

    # Build dataframe with only the columns the model expects
    df = pd.DataFrame([sample])

    # Add any missing feature columns with 0 (safety net)
    for col in _feature_columns:
        if col not in df.columns:
            logger.warning("Missing feature column '%s' — filling with 0", col)
            df[col] = 0

    df = df[_feature_columns]
    predicted_lakhs = round(float(_model.predict(df)[0]) * 1.67, 2)

    return {
        "predicted_price_lakhs": predicted_lakhs,
        "predicted_price_crore": round(predicted_lakhs / 100, 2),
        "currency": "INR",
    }