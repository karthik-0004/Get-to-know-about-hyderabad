"""
Google Places API – Legacy Nearby Search
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Uses the standard Nearby Search endpoint (GET):
    https://maps.googleapis.com/maps/api/place/nearbysearch/json

This is part of the **Places API** (not "Places API (New)").
Make sure the *Places API* is enabled in your Google Cloud Console.
"""

from __future__ import annotations

import math
import os
import re
from typing import Any

import requests

# ── Legacy Nearby Search endpoint (GET, query-param auth) ──────────────
NEARBY_SEARCH_URL = (
    "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
)
PHOTO_URL_TEMPLATE = (
    "https://maps.googleapis.com/maps/api/place/photo"
    "?maxheight=400&photo_reference={ref}&key={key}"
)
SEARCH_RADIUS_DEFAULT = 3000
SEARCH_RADIUS_METERS = SEARCH_RADIUS_DEFAULT  # backward-compat alias
MAX_RESULTS_PER_CATEGORY = 5

# Earth's mean radius in metres (WGS-84)
_EARTH_RADIUS_M = 6_371_000


# ── Exceptions ─────────────────────────────────────────────────────────
class PlacesServiceError(Exception):
    """Base error for anything Places-related."""


class PlacesTimeoutError(PlacesServiceError):
    pass


class PlacesNetworkError(PlacesServiceError):
    pass


class PlacesAuthError(PlacesServiceError):
    pass


class PlacesAPIError(PlacesServiceError):
    """Wraps a non-200 response from the Google Places API."""

    def __init__(self, status_code: int, body: str):
        self.status_code = status_code
        self.body = body
        super().__init__(
            f"Google Places API returned HTTP {status_code}: {body[:300]}"
        )


# ── Helpers ────────────────────────────────────────────────────────────
def _get_api_key() -> str:
    key = os.environ.get("GOOGLE_PLACES_API_KEY", "")
    if not key:
        raise PlacesServiceError("GOOGLE_PLACES_API_KEY is not set")
    return key


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Return the great-circle distance in **metres** between two points
    on Earth using the Haversine formula.

    The Haversine formula accounts for Earth's curvature:
        a = sin²(Δφ/2) + cos(φ1) · cos(φ2) · sin²(Δλ/2)
        c = 2 · atan2(√a, √(1−a))
        d = R · c

    where φ = latitude in radians, λ = longitude in radians, R = Earth radius.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return _EARTH_RADIUS_M * c


def _search_nearby(
    lat: float,
    lng: float,
    place_type: str,
    radius_meters: int = SEARCH_RADIUS_DEFAULT,
    keyword: str | None = None,
) -> list[dict[str, Any]]:
    """Call the legacy Nearby Search endpoint (GET with query params)."""

    api_key = _get_api_key()

    params: dict[str, Any] = {
        "location": f"{lat},{lng}",
        "radius": radius_meters,
        "type": place_type,
        "key": api_key,
    }
    if keyword:
        params["keyword"] = keyword

    try:
        response = requests.get(
            NEARBY_SEARCH_URL,
            params=params,
            timeout=10,
        )
    except requests.exceptions.Timeout as exc:
        raise PlacesTimeoutError("Google Places request timed out") from exc
    except requests.exceptions.RequestException as exc:
        raise PlacesNetworkError(
            f"Failed to reach Google Places API: {exc}"
        ) from exc

    # ── Debug logging (visible in the Django runserver console) ──
    if not response.ok:
        print(f"[Places API] HTTP {response.status_code}")
        print(f"[Places API] Response body: {response.text[:500]}")
        if response.status_code in (401, 403):
            raise PlacesAuthError(
                "Invalid or restricted Google API key "
                f"(HTTP {response.status_code})"
            )
        raise PlacesAPIError(response.status_code, response.text)

    data: dict = response.json()

    # The legacy API returns its own status field inside the JSON.
    api_status = data.get("status", "")
    if api_status not in ("OK", "ZERO_RESULTS"):
        error_msg = data.get("error_message", api_status)
        print(f"[Places API] API status: {api_status} – {error_msg}")
        if api_status == "REQUEST_DENIED":
            raise PlacesAuthError(f"Google API request denied: {error_msg}")
        raise PlacesServiceError(
            f"Google Places API error: {api_status} – {error_msg}"
        )

    return data.get("results", [])


def _build_photo_url(photo_reference: str) -> str:
    """Build a direct photo URL using the legacy Place Photos endpoint."""
    if not photo_reference:
        return ""
    return PHOTO_URL_TEMPLATE.format(ref=photo_reference, key=_get_api_key())


def _format_place(
    place: dict[str, Any],
    *,
    origin_lat: float | None = None,
    origin_lng: float | None = None,
) -> dict[str, Any]:
    """Normalise a legacy Nearby Search result into our frontend shape."""
    location = place.get("geometry", {}).get("location", {})
    photos = place.get("photos", [])

    photo_ref = ""
    if photos:
        photo_ref = photos[0].get("photo_reference", "")

    place_lat = location.get("lat")
    place_lng = location.get("lng")

    formatted: dict[str, Any] = {
        "name": place.get("name", ""),
        "rating": place.get("rating"),
        "formatted_address": place.get("vicinity", ""),
        "location": {
            "lat": place_lat,
            "lng": place_lng,
        },
        "place_id": place.get("place_id", ""),
        "photo_url": _build_photo_url(photo_ref),
    }

    # Attach distance (m) when origin is provided
    if (
        origin_lat is not None
        and origin_lng is not None
        and place_lat is not None
        and place_lng is not None
    ):
        formatted["distance_m"] = round(
            _haversine(origin_lat, origin_lng, place_lat, place_lng)
        )

    return formatted


def _sorted_by_rating(places: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        places,
        key=lambda p: p.get("rating") or 0,
        reverse=True,
    )


def _sorted_by_distance(places: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        places,
        key=lambda p: p.get("distance_m", float("inf")),
    )


# ── Quality-filter helpers ─────────────────────────────────────────────

def _name_matches_any(name: str, patterns: list[str]) -> bool:
    """Return True if *name* contains any of the blacklist words (case-insensitive)."""
    lowered = name.lower()
    return any(re.search(rf"\b{re.escape(p)}\b", lowered) for p in patterns)


def _filter_places(
    results: list[dict[str, Any]],
    *,
    min_rating: float = 0.0,
    exclude_words: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Drop results below *min_rating* or whose name matches *exclude_words*."""
    filtered: list[dict[str, Any]] = []
    for place in results:
        rating = place.get("rating") or 0.0
        if rating < min_rating:
            continue
        if exclude_words and _name_matches_any(place.get("name", ""), exclude_words):
            continue
        filtered.append(place)
    return filtered


# ── Per-category configuration ─────────────────────────────────────────

_CATEGORY_CONFIG: list[dict[str, Any]] = [
    {
        "key": "hospitals",
        "place_type": "hospital",
        "keyword": "hospital",
        "radius": 5000,
        "min_rating": 3.0,
        "exclude": [
            "pharmacy", "medical store", "chemist", "diagnostic",
            "lab", "pathology", "medicals", "drug",
        ],
    },
    {
        "key": "malls",
        "place_type": "shopping_mall",
        "keyword": "shopping mall",
        "radius": 5000,
        "min_rating": 3.0,
        "exclude": [
            "store", "shop", "mart", "supermarket", "general",
            "kirana", "fancy", "medical", "wholesale", "retail",
            "stationery", "provision",
        ],
    },
    {
        "key": "cinemas",
        "place_type": "movie_theater",
        "keyword": "cinema",
        "radius": 5000,
        "min_rating": 3.0,
        "exclude": [],
    },
    {
        "key": "schools",
        "place_type": "school",
        "keyword": "school",
        "radius": 5000,
        "min_rating": 3.0,
        "exclude": ["tuition", "coaching", "tutorial"],
    },
    {
        "key": "hotels",
        "place_type": "lodging",
        "keyword": "hotel",
        "radius": 5000,
        "min_rating": 0.0,
        "exclude": [
            "lodge", "paying guest", "pg", "hostel", "dormitory",
            "dharamshala", "guest house",
        ],
    },
    {
        "key": "restaurants",
        "place_type": "restaurant",
        "keyword": "restaurant",
        "radius": 5000,
        "min_rating": 0.0,
        "exclude": [
            "stall", "pani puri", "chaat", "thela", "cart",
            "tiffin", "mess", "dhaba", "juice",
        ],
    },
    {
        "key": "bus_stops",
        "place_type": "bus_station",
        "keyword": None,
        "radius": 5000,
        "min_rating": 0.0,
        "exclude": [],
    },
    {
        "key": "metro_stations",
        "place_type": "subway_station",
        "keyword": "metro station",
        "radius": 5000,
        "min_rating": 0.0,
        "exclude": [],
    },
]


# ── Public entry point ─────────────────────────────────────────────────

def analyze_area(lat: float, lng: float) -> dict[str, Any]:
    result: dict[str, Any] = {}

    # ── Top-5-by-rating categories (with quality filters) ───────
    for cfg in _CATEGORY_CONFIG:
        raw = _search_nearby(
            lat=lat,
            lng=lng,
            place_type=cfg["place_type"],
            radius_meters=cfg.get("radius", SEARCH_RADIUS_DEFAULT),
            keyword=cfg.get("keyword"),
        )
        cleaned = _filter_places(
            raw,
            min_rating=cfg.get("min_rating", 0.0),
            exclude_words=cfg.get("exclude"),
        )
        formatted = [_format_place(p, origin_lat=lat, origin_lng=lng) for p in cleaned]
        result[cfg["key"]] = _sorted_by_rating(formatted)

    # ── Nearest railway station (single object, sorted by distance) ──
    raw_trains = _search_nearby(lat=lat, lng=lng, place_type="train_station")
    formatted_trains = [
        _format_place(p, origin_lat=lat, origin_lng=lng) for p in raw_trains
    ]
    sorted_trains = _sorted_by_distance(formatted_trains)
    result["nearest_railway_station"] = sorted_trains[0] if sorted_trains else None

    return result
