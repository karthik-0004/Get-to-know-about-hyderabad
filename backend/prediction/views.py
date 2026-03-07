import json
import os

import joblib
import numpy as np
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt


ML_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ml_models")

# ── in-memory cache so we only read .pkl files once ──────────────────────
_cache: dict = {}


def _load(name: str):
    """Load the artefact bundle for *name*, with caching."""
    if name in _cache:
        return _cache[name]

    artefacts = joblib.load(os.path.join(ML_DIR, f"{name}_model.pkl"))
    localities = joblib.load(os.path.join(ML_DIR, f"{name}_localities.pkl"))
    artefacts["localities"] = localities

    _cache[name] = artefacts
    return artefacts


def _build_features(bundle, locality: str, bhk, sqft: float):
    """
    Build the feature vector matching train_models.py v2 column order:
      [locality_te, sqft, (bhk?), avg_price_sqft, min_price_sqft,
       max_price_sqft, price_range_sqft, estimated_price]
    """
    # Locality target-encoded value
    loc_te = bundle["loc_target_map"].get(locality, bundle["loc_global_mean"])

    # Locality price-per-sqft stats
    stats = bundle["locality_stats"].get(locality, bundle["median_stats"])
    avg_ps = stats["avg_price_sqft"]
    min_ps = stats["min_price_sqft"]
    max_ps = stats["max_price_sqft"]

    # Engineered
    price_range = max_ps - min_ps
    estimated_price = sqft * avg_ps

    if bundle["has_bhk"]:
        return np.array([[loc_te, sqft, bhk, avg_ps, min_ps, max_ps, price_range, estimated_price]])
    else:
        return np.array([[loc_te, sqft, avg_ps, min_ps, max_ps, price_range, estimated_price]])


VALID_TYPES = {"apartment", "villa", "independent_house", "plot"}
HAS_BHK = {"apartment": True, "villa": True, "independent_house": True, "plot": False}


@method_decorator(csrf_exempt, name="dispatch")
class PredictPriceView(View):
    """POST /api/predict/  — returns a price estimate."""

    def post(self, request):
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        locality = (body.get("locality") or "").strip()
        property_type = (body.get("property_type") or "").strip().lower()
        bhk = body.get("bhk")
        sqft = body.get("sqft")

        # ── validation ────────────────────────────────────────────────────
        if property_type not in VALID_TYPES:
            return JsonResponse(
                {"error": f"property_type must be one of {sorted(VALID_TYPES)}"},
                status=400,
            )
        if not sqft or float(sqft) <= 0:
            return JsonResponse({"error": "sqft is required and must be > 0"}, status=400)
        sqft = float(sqft)

        if HAS_BHK[property_type]:
            if bhk is None:
                return JsonResponse({"error": "bhk is required for this property type"}, status=400)
            bhk = int(bhk)

        # ── choose primary or backup ─────────────────────────────────────
        try:
            primary = _load(property_type)
        except FileNotFoundError:
            primary = None

        use_backup = False
        if primary and locality in primary["localities"]:
            bundle = primary
            model_used = f"{property_type}_model"
        else:
            bundle = _load("backup")
            model_used = "backup_model"
            use_backup = True

        locality_found = not use_backup

        # For backup model (has_bhk=True), if property is plot send bhk=0
        effective_bhk = bhk if bhk else (0 if use_backup else bhk)

        # ── sqft range for the locality ────────────────────────────────────
        loc_stats = bundle["locality_stats"].get(locality, bundle["median_stats"])
        min_sqft = int(loc_stats.get("min_sqft", 0))
        max_sqft = int(loc_stats.get("max_sqft", 0))

        # ── build features & predict ──────────────────────────────────────
        try:
            features = _build_features(bundle, locality, effective_bhk, sqft)
            pred_log = bundle["model"].predict(features)[0]
            predicted = float(np.expm1(pred_log))  # undo log1p transform
        except Exception as exc:
            return JsonResponse(
                {"error": f"Prediction failed: {exc}"}, status=500
            )

        return JsonResponse({
            "predicted_price": round(predicted, 2),
            "model_used": model_used,
            "locality_found": locality_found,
            "sqft_range": {"min": min_sqft, "max": max_sqft},
            "message": "Prediction successful",
        })


# ══════════════════════════════════════════════════════════════════════════
#  Rental prediction
# ══════════════════════════════════════════════════════════════════════════

_rent_cache: dict = {}

# Map frontend values → values used during training
FURNISHING_MAP = {
    "furnished": "Fully Furnished",
    "semi-furnished": "Semi Furnished",
    "unfurnished": "Unknown",
}

PROPERTY_TYPE_MAP = {
    "flat": "Flat",
    "independent house": "Independent House",
    "builder floor": "Other",
}


def _load_rent(name: str):
    """Load rental model + encoder + localities + meta, with caching."""
    if name in _rent_cache:
        return _rent_cache[name]

    model = joblib.load(os.path.join(ML_DIR, f"{name}_model.pkl"))
    encoder = joblib.load(os.path.join(ML_DIR, f"{name}_encoder.pkl"))
    localities = joblib.load(os.path.join(ML_DIR, f"{name}_localities.pkl"))
    meta = joblib.load(os.path.join(ML_DIR, f"{name}_meta.pkl"))

    bundle = {
        "model": model,
        "encoder": encoder,
        "localities": localities,
        **meta,  # locality_stats, median_stats, has_bhk
    }
    _rent_cache[name] = bundle
    return bundle


VALID_BHK = {"1bhk", "2bhk", "3bhk"}


@method_decorator(csrf_exempt, name="dispatch")
class PredictRentView(View):
    """POST /api/predict/rent/  — returns a monthly rent estimate."""

    def post(self, request):
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        locality = (body.get("locality") or "").strip()
        bhk_key = (body.get("bhk") or "").strip().lower()
        sqft = body.get("sqft")
        furnishing = (body.get("furnishing") or "").strip().lower()
        property_type = (body.get("property_type") or "").strip().lower()

        # ── validation ────────────────────────────────────────────────────
        if bhk_key not in VALID_BHK:
            return JsonResponse(
                {"error": f"bhk must be one of {sorted(VALID_BHK)}"}, status=400
            )
        if not sqft or float(sqft) <= 0:
            return JsonResponse({"error": "sqft is required and must be > 0"}, status=400)
        sqft = float(sqft)

        furnishing_val = FURNISHING_MAP.get(furnishing)
        if furnishing_val is None:
            return JsonResponse(
                {"error": f"furnishing must be one of: {list(FURNISHING_MAP.keys())}"}, status=400
            )

        prop_val = PROPERTY_TYPE_MAP.get(property_type)
        if prop_val is None:
            return JsonResponse(
                {"error": f"property_type must be one of: {list(PROPERTY_TYPE_MAP.keys())}"}, status=400
            )

        # ── choose primary or fallback ────────────────────────────────────
        model_name = f"rent_{bhk_key}"
        try:
            primary = _load_rent(model_name)
        except FileNotFoundError:
            primary = None

        use_backup = False
        if primary and locality in primary["localities"]:
            bundle = primary
            model_used = f"{model_name}_model"
        else:
            bundle = _load_rent("rent_backup")
            model_used = "rent_backup_model"
            use_backup = True

        locality_found = not use_backup

        # ── rent stats for the locality ────────────────────────────────────
        stats = bundle["locality_stats"].get(locality, bundle["median_stats"])
        avg_rent = stats["avg_rent"]
        min_rent = stats["min_rent"]
        max_rent = stats["max_rent"]

        # ── encode features & predict ──────────────────────────────────────
        try:
            enc = bundle["encoder"]
            # Encode categorical columns: [Locality, Furnishing, Property Type]
            cat_encoded = enc.transform([[locality, furnishing_val, prop_val]])[0]

            if bundle["has_bhk"]:
                # backup model: [locality_enc, sqft, bhk, furnishing_enc, prop_enc, avg, min, max]
                bhk_num = int(bhk_key[0])
                features = np.array([[
                    cat_encoded[0], sqft, bhk_num, cat_encoded[1], cat_encoded[2],
                    avg_rent, min_rent, max_rent,
                ]])
            else:
                # per-bhk model: [locality_enc, sqft, furnishing_enc, prop_enc, avg, min, max]
                features = np.array([[
                    cat_encoded[0], sqft, cat_encoded[1], cat_encoded[2],
                    avg_rent, min_rent, max_rent,
                ]])

            predicted = float(bundle["model"].predict(features)[0])
            predicted = max(predicted, 0)
        except Exception as exc:
            return JsonResponse(
                {"error": f"Prediction failed: {exc}"}, status=500
            )

        return JsonResponse({
            "predicted_rent": round(predicted, 2),
            "model_used": model_used,
            "locality_found": locality_found,
            "message": "Rental prediction successful",
        })
