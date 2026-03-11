"""
Locality enrichment service — live scoring via Overpass API (OpenStreetMap).

Uses ultra-lightweight individual ``out count`` queries so the public
Overpass servers respond quickly.  Includes mirror fallback and an
in-memory LRU cache.  When Overpass is completely unavailable the service
returns scores based on metro distance and IT-hub distance alone.
"""

import logging
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Mirror list — tried in order; first success wins.
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
]

SEARCH_RADIUS_M = 1500      # metres for POI counts
ROAD_RADIUS_M   = 500       # metres for road density

# Hitech City coordinates (IT hub reference point)
_IT_HUB_LAT = 17.4435
_IT_HUB_LNG = 78.3772


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _bbox(lat: float, lng: float, radius_m: int) -> str:
    """Return 'south,west,north,east' bbox string for Overpass."""
    d_lat = radius_m / 111_320
    d_lng = radius_m / (111_320 * math.cos(math.radians(lat)))
    return f"{lat - d_lat},{lng - d_lng},{lat + d_lat},{lng + d_lng}"


def _single_count(bbox: str, tag_filter: str) -> int:
    """Run one tiny count query across mirrors. Returns 0 on total failure."""
    query = (
        f'[out:json][timeout:5];'
        f'node({bbox}){tag_filter};'
        f'out count;'
    )
    for url in OVERPASS_URLS:
        try:
            resp = requests.post(
                url,
                data={"data": query},
                timeout=6,
                headers={"Accept": "application/json"},
            )
            if resp.status_code in (429, 504, 503):
                continue
            resp.raise_for_status()
            for el in resp.json().get("elements", []):
                cnt = el.get("tags", {}).get("total")
                if cnt is not None:
                    return int(cnt)
            return 0
        except Exception:
            continue
    return -1   # sentinel: all mirrors failed


# ---------------------------------------------------------------------------
# POI counts — individual queries run in parallel threads
# ---------------------------------------------------------------------------

_POI_QUERIES = [
    ("hospital_count", '["amenity"~"^(hospital|clinic)$"]',          "search"),
    ("school_count",   '["amenity"~"^(school|college|university)$"]', "search"),
    ("mall_count",     '["shop"~"^(mall|supermarket)$"]',            "search"),
    ("park_count",     '["leisure"~"^(park|garden)$"]',              "search"),
    ("road_density",   '["highway"~"^(primary|secondary|tertiary|residential)$"]', "road"),
]


def _fetch_poi_counts(lat: float, lng: float) -> dict[str, int]:
    """Fire individual count queries in parallel — much lighter per request."""
    bb_search = _bbox(lat, lng, SEARCH_RADIUS_M)
    bb_road = _bbox(lat, lng, ROAD_RADIUS_M)

    results = {}
    all_failed = True

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {}
        for key, tag, kind in _POI_QUERIES:
            bb = bb_road if kind == "road" else bb_search
            futures[pool.submit(_single_count, bb, tag)] = key

        try:
            for future in as_completed(futures, timeout=28):
                key = futures[future]
                try:
                    val = future.result()
                    if val >= 0:
                        all_failed = False
                    results[key] = max(val, 0)
                except Exception:
                    results[key] = 0
        except TimeoutError:
            # Collect whatever finished so far, cancel the rest
            for f, key in futures.items():
                if f.done():
                    try:
                        val = f.result()
                        if val >= 0:
                            all_failed = False
                        results[key] = max(val, 0)
                    except Exception:
                        results.setdefault(key, 0)
                else:
                    f.cancel()

    # Fill any missing keys
    for key, _, _ in _POI_QUERIES:
        results.setdefault(key, 0)

    results["_overpass_available"] = not all_failed
    return results


# ---------------------------------------------------------------------------
# Metro distance — hardcoded Hyderabad Metro stations (instant)
# ---------------------------------------------------------------------------

_METRO_STATIONS = [
    # Red Line (Miyapur – LB Nagar)
    (17.4969, 78.3584), (17.4889, 78.3716), (17.4854, 78.3808),
    (17.4822, 78.3881), (17.4762, 78.3983), (17.4679, 78.4078),
    (17.4585, 78.4155), (17.4507, 78.4226), (17.4435, 78.4307),
    (17.4382, 78.4392), (17.4342, 78.4485), (17.4277, 78.4533),
    (17.4193, 78.4580), (17.4115, 78.4601), (17.4012, 78.4635),
    (17.3937, 78.4726), (17.3860, 78.4790), (17.3783, 78.4858),
    (17.3720, 78.4896), (17.3660, 78.4928), (17.3595, 78.4970),
    (17.3527, 78.5035), (17.3472, 78.5109), (17.3412, 78.5175),
    (17.3390, 78.5268), (17.3440, 78.5410), (17.3475, 78.5538),
    # Blue Line (Nagole – Raidurg)
    (17.3945, 78.5635), (17.3949, 78.5485), (17.3982, 78.5318),
    (17.3997, 78.5200), (17.3998, 78.5069), (17.3975, 78.4965),
    (17.3992, 78.4858), (17.4041, 78.4745), (17.4106, 78.4655),
    (17.4362, 78.4485), (17.4437, 78.4395), (17.4507, 78.4286),
    (17.4535, 78.4153), (17.4502, 78.4032), (17.4459, 78.3914),
    (17.4418, 78.3819), (17.4373, 78.3726), (17.4268, 78.3635),
    (17.4185, 78.3565),
]


def _nearest_metro_distance_km(lat: float, lng: float) -> float:
    best = min((_haversine_km(lat, lng, s_lat, s_lng)
                for s_lat, s_lng in _METRO_STATIONS), default=50.0)
    return round(best, 4)


# ---------------------------------------------------------------------------
# Score derivation
# ---------------------------------------------------------------------------

def _amenity_score(h: int, s: int, m: int, p: int) -> float:
    raw = (min(h, 30) / 30 * 2.5
           + min(s, 20) / 20 * 2.5
           + min(m, 10) / 10 * 2.5
           + min(p, 20) / 20 * 2.5)
    return round(min(raw, 10.0), 2)


def _connectivity_score(metro_km: float, road_count: float) -> float:
    metro_pts = max(0, 5 * (1 - metro_km / 15))
    road_pts = min(5, road_count / 200 * 5)
    return round(min(metro_pts + road_pts, 10.0), 2)


# ---------------------------------------------------------------------------
# In-memory cache — rounds coords to ~110 m grid so nearby clicks reuse data
# ---------------------------------------------------------------------------

@lru_cache(maxsize=256)
def _cached_poi_counts(lat_r: float, lng_r: float) -> dict:
    """Cached wrapper: lat_r / lng_r are already rounded."""
    return _fetch_poi_counts(lat_r, lng_r)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_locality_scores(address: str, lat: float | None = None,
                        lng: float | None = None) -> dict | None:
    """Return live locality scores for (lat, lng) using Overpass + hardcoded metro.

    Always returns a result — even when Overpass is completely down, the
    metro-distance and IT-hub-distance scores are computed locally.
    """
    if lat is None or lng is None:
        return None

    try:
        # Round to ~110 m grid for caching
        lat_r = round(lat, 3)
        lng_r = round(lng, 3)

        # Overpass request (cached) — may return zeros if servers are down
        data = _cached_poi_counts(lat_r, lng_r)
        overpass_ok = data.get("_overpass_available", False)

        # Instant calculations (no external API)
        metro_km = _nearest_metro_distance_km(lat, lng)
        it_hub_km = round(_haversine_km(lat, lng, _IT_HUB_LAT, _IT_HUB_LNG), 4)

        amenity = _amenity_score(
            data["hospital_count"], data["school_count"],
            data["mall_count"], data["park_count"],
        )
        connectivity = _connectivity_score(metro_km, data.get("road_density", 0))

        locality_name = address.strip().split(",")[0].strip() if address else "Selected Area"

        method = "live_overpass" if overpass_ok else "local_estimate"
        if not overpass_ok:
            logger.warning("Overpass unavailable — returning local-only scores")

        return {
            "locality": locality_name,
            "amenity_score": amenity,
            "connectivity_score": connectivity,
            "metro_distance_km": metro_km,
            "it_hub_distance_km": it_hub_km,
            "hospital_count": data["hospital_count"],
            "school_count": data["school_count"],
            "mall_count": data["mall_count"],
            "park_count": data["park_count"],
            "road_density": data.get("road_density", 0),
            "match_method": method,
        }
    except Exception as exc:
        logger.exception("Live locality scoring failed: %s", exc)
        # Last-resort fallback — return at least metro/IT-hub scores
        try:
            metro_km = _nearest_metro_distance_km(lat, lng)
            it_hub_km = round(_haversine_km(lat, lng, _IT_HUB_LAT, _IT_HUB_LNG), 4)
            locality_name = address.strip().split(",")[0].strip() if address else "Selected Area"
            connectivity = _connectivity_score(metro_km, 0)
            return {
                "locality": locality_name,
                "amenity_score": 0,
                "connectivity_score": connectivity,
                "metro_distance_km": metro_km,
                "it_hub_distance_km": it_hub_km,
                "hospital_count": 0,
                "school_count": 0,
                "mall_count": 0,
                "park_count": 0,
                "road_density": 0,
                "match_method": "local_fallback",
            }
        except Exception:
            return None
