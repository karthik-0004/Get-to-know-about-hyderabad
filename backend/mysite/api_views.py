import json
import os
import re
from concurrent.futures import ThreadPoolExecutor

import joblib
import openpyxl
import requests as http_requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from dotenv import load_dotenv

from . import usage_counter

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

from django.http import HttpResponse

from .places_service import (
    SEARCH_RADIUS_METERS,
    PlacesAPIError,
    PlacesAuthError,
    PlacesNetworkError,
    PlacesServiceError,
    PlacesTimeoutError,
    analyze_area as fetch_nearby_places,
    fetch_photo_bytes,
)
from .locality_service import get_locality_scores

ML_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prediction", "ml_models")
SCRAPPED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scrapped_data")


# ── Place-photo proxy (keeps API key server-side) ─────────────────────
@require_http_methods(["GET"])
def place_photo(request):
    ref = request.GET.get("ref", "").strip()
    if not ref:
        return JsonResponse({"error": "Missing ref parameter"}, status=400)
    try:
        image_bytes, content_type = fetch_photo_bytes(ref)
        response = HttpResponse(image_bytes, content_type=content_type)
        response["Cache-Control"] = "public, max-age=86400"
        return response
    except Exception:
        return HttpResponse(status=502)


def _to_float(value, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"'{field_name}' must be a valid number") from exc


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def analyze_area(request):
    if request.method == "OPTIONS":
        return JsonResponse({}, status=200)

    # ── Daily API usage limit check ────────────────────────────────────
    if usage_counter.is_limit_reached():
        counter_info = usage_counter.get_usage()
        return JsonResponse(
            {
                "error": "daily_limit_reached",
                "message": f"Daily API limit of {counter_info['limit']} reached. Try again tomorrow.",
                "usage": counter_info,
            },
            status=429,
        )

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    if not isinstance(payload, dict):
        return JsonResponse({"error": "JSON body must be an object"}, status=400)

    try:
        lat = _to_float(payload.get("lat"), "lat")
        lng = _to_float(payload.get("lng"), "lng")
        raw_address = (
            payload.get("address")
            or payload.get("name")
            or payload.get("locality")
        )

        if isinstance(raw_address, str) and raw_address.strip():
            address = raw_address.strip()
        else:
            # Fallback lets coordinate-only requests succeed.
            address = f"{lat:.5f}, {lng:.5f}"
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    # Run Google Places and Overpass locality scores in parallel
    with ThreadPoolExecutor(max_workers=2) as pool:
        places_future = pool.submit(fetch_nearby_places, lat=lat, lng=lng)
        scores_future = pool.submit(get_locality_scores, address, lat=lat, lng=lng)

        # Collect locality scores (never fail the whole request)
        try:
            locality_scores = scores_future.result(timeout=35)
        except Exception as exc:
            print(f"[analyze_area] Locality scores failed: {exc}")
            locality_scores = None

        # Collect places (can fail)
        try:
            places = places_future.result(timeout=30)
        except PlacesTimeoutError:
            return JsonResponse(
                {"error": "Google Places API timeout. Please try again."},
                status=504,
            )
        except PlacesAuthError as exc:
            print(f"[analyze_area] Auth error: {exc}")
            return JsonResponse(
                {"error": f"Google API key is invalid or restricted: {exc}"},
                status=403,
            )
        except PlacesAPIError as exc:
            print(f"[analyze_area] API error HTTP {exc.status_code}: {exc.body[:300]}")
            return JsonResponse(
                {
                    "error": f"Google Places API returned HTTP {exc.status_code}",
                    "detail": exc.body[:500],
                },
                status=502,
            )
        except PlacesNetworkError as exc:
            print(f"[analyze_area] Network error: {exc}")
            return JsonResponse(
                {"error": f"Network failure while calling Google Places API: {exc}"},
                status=503,
            )
        except PlacesServiceError as exc:
            print(f"[analyze_area] Service error: {exc}")
            return JsonResponse({"error": str(exc)}, status=502)
        except Exception as exc:
            print(f"[analyze_area] Unexpected: {exc}")
            return JsonResponse({"error": str(exc)}, status=500)

    # ── Increment counter after successful Places fetch ──────────────
    counter_info = usage_counter.increment()

    return JsonResponse(
        {
            "area": address,
            "coordinates": {"lat": lat, "lng": lng},
            "radius_meters": SEARCH_RADIUS_METERS,
            "locality_scores": locality_scores,
            "usage": counter_info,
            **places,   # hospitals, malls, cinemas, schools, etc.
        },
        status=200,
    )


# ══════════════════════════════════════════════════════════════════════════
#  Market Pulse — avg price/sqft from ML model locality_stats
# ══════════════════════════════════════════════════════════════════════════
_mp_cache: dict = {}


def _load_model_bundle(name: str):
    if name in _mp_cache:
        return _mp_cache[name]
    model_path = os.path.join(ML_DIR, f"{name}_model.pkl")
    loc_path = os.path.join(ML_DIR, f"{name}_localities.pkl")
    if not os.path.exists(model_path):
        return None
    bundle = joblib.load(model_path)
    bundle["localities"] = joblib.load(loc_path)
    _mp_cache[name] = bundle
    return bundle


def _groq_market_pulse(locality: str):
    """Call Groq to get an estimated avg price per sqft for a locality."""
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        return None

    prompt = (
        f"What is the current average residential property price per square foot "
        f"in {locality}, Hyderabad, India in Indian Rupees for 2025-2026? "
        f"Return ONLY a single numeric value (no commas, no currency symbol, no text). "
        f"Example: 7500"
    )

    try:
        resp = http_requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": "You are a Hyderabad real estate market expert. Respond with only a numeric price per sqft value in INR."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 30,
            },
            timeout=12,
        )
        resp.raise_for_status()
        data = resp.json()
        answer = data["choices"][0]["message"]["content"].strip()
        numbers = re.findall(r"[\d]+\.?\d*", answer.replace(",", ""))
        if numbers:
            price = float(numbers[0])
            if price > 0:
                return price
    except Exception:
        pass
    return None


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def market_pulse(request):
    if request.method == "OPTIONS":
        return JsonResponse({}, status=200)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    locality = (payload.get("locality") or "").strip()
    if not locality:
        return JsonResponse({"error": "locality is required"}, status=400)

    result = {}
    for ptype in ("apartment", "villa", "independent_house", "plot"):
        bundle = _load_model_bundle(ptype)
        if not bundle:
            continue
        stats = bundle.get("locality_stats", {}).get(locality)
        if stats:
            result[ptype] = {
                "avg_price_sqft": round(stats["avg_price_sqft"]),
                "min_price_sqft": round(stats["min_price_sqft"]),
                "max_price_sqft": round(stats["max_price_sqft"]),
            }

    # Fallback: try backup model
    if not result:
        backup = _load_model_bundle("backup")
        if backup:
            stats = backup.get("locality_stats", {}).get(locality)
            if stats:
                result["general"] = {
                    "avg_price_sqft": round(stats["avg_price_sqft"]),
                    "min_price_sqft": round(stats["min_price_sqft"]),
                    "max_price_sqft": round(stats["max_price_sqft"]),
                }

    # Fallback: Groq AI estimate if no data found anywhere
    if not result:
        ai_price = _groq_market_pulse(locality)
        if ai_price is not None:
            result["general"] = {
                "avg_price_sqft": round(ai_price),
                "min_price_sqft": None,
                "max_price_sqft": None,
            }

    return JsonResponse({"locality": locality, "price_data": result})


# ══════════════════════════════════════════════════════════════════════════
#  Nearby Listings — 2-3 listings from scrapped xlsx data
# ══════════════════════════════════════════════════════════════════════════
_listings_cache: dict = {}

XLSX_FILES = {
    "apartment": "apartment_data_cleaned.xlsx",
    "villa": "villa_cleaned.xlsx",
    "independent_house": "independent_house_cleaned.xlsx",
    "plot": "plot_cleaned.xlsx",
}


def _load_xlsx(filename: str):
    if filename in _listings_cache:
        return _listings_cache[filename]
    filepath = os.path.join(SCRAPPED_DIR, filename)
    if not os.path.exists(filepath):
        return []
    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    wb.close()
    _listings_cache[filename] = rows
    return rows


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def nearby_listings(request):
    if request.method == "OPTIONS":
        return JsonResponse({}, status=200)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    locality = (payload.get("locality") or "").strip()
    if not locality:
        return JsonResponse({"error": "locality is required"}, status=400)

    locality_lower = locality.lower()
    listings = []

    for ptype, fname in XLSX_FILES.items():
        rows = _load_xlsx(fname)
        # Column order: Locality, BHK, Sqft, AvgPrice/Sqft, MinPrice/Sqft, MaxPrice/Sqft, Price
        for row in rows:
            if not row or not row[0]:
                continue
            if str(row[0]).strip().lower() == locality_lower:
                price = row[6] if len(row) > 6 and row[6] else 0
                listings.append({
                    "type": ptype.replace("_", " ").title(),
                    "locality": str(row[0]).strip(),
                    "bhk": row[1] if len(row) > 1 else None,
                    "sqft": row[2] if len(row) > 2 else None,
                    "price": price,
                    "avg_price_sqft": row[3] if len(row) > 3 else None,
                })
            if len(listings) >= 6:
                break
        if len(listings) >= 6:
            break

    # Return top 3 listings, prefer variety of types
    seen_types = set()
    diverse = []
    for l in listings:
        if l["type"] not in seen_types:
            diverse.append(l)
            seen_types.add(l["type"])
        if len(diverse) >= 3:
            break
    # Fill remaining slots
    if len(diverse) < 3:
        for l in listings:
            if l not in diverse:
                diverse.append(l)
            if len(diverse) >= 3:
                break

    return JsonResponse({"locality": locality, "listings": diverse})


# ══════════════════════════════════════════════════════════════════════════
#  Daily API Usage Counter
# ══════════════════════════════════════════════════════════════════════════
@require_http_methods(["GET"])
def api_usage_counter(request):
    """Return the current daily API usage count and limit."""
    return JsonResponse(usage_counter.get_usage())