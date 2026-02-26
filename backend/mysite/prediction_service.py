"""
Prediction service — loads the trained ML model and encoders once at import
time and exposes a predict_price() function for the API layer.
"""

import pickle
import logging

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


def _safe_encode(encoder_key: str, value: str) -> int:
    """Encode a categorical value using the saved LabelEncoder.

    If the label was never seen during training, fall back to the
    most-frequent class (index 0) instead of crashing.
    """
    encoder = _encoders[encoder_key]
    if value in encoder.classes_:
        return int(encoder.transform([value])[0])
    logger.warning(
        "Unseen label '%s' for encoder '%s' — using fallback (index 0)",
        value,
        encoder_key,
    )
    return 0


def predict_price(
    locality: str,
    area_sqft: float,
    bhk: int,
    bathrooms: int,
    property_type: str,
    furnishing: str,
) -> dict:
    """Return a prediction dict with price in Lakhs and Crore."""
    import pandas as pd

    sample = {
        "Locality_enc": _safe_encode("Locality", locality),
        "Area_SqFt": float(area_sqft),
        "BHK_num": int(bhk),
        "Bathrooms": int(bathrooms),
        "Property Type_enc": _safe_encode("Property Type", property_type),
        "Furnishing_enc": _safe_encode("Furnishing", furnishing),
    }

    df = pd.DataFrame([sample])[_feature_columns]
    predicted_lakhs = round(float(_model.predict(df)[0]), 2)

    return {
        "predicted_price_lakhs": predicted_lakhs,
        "predicted_price_crore": round(predicted_lakhs / 100, 2),
        "currency": "INR",
    }
