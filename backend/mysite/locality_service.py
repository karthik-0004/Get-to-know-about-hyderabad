"""
Locality enrichment service — live scoring via Overpass API (OpenStreetMap).

Uses ultra-lightweight bbox + ``out count`` queries so the public Overpass
servers respond quickly.  Includes retry-with-backoff, mirror fallback, and
an in-memory LRU cache to avoid repeat hits for the same area.
"""

import logging
import math
import time
from functools import lru_cache
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Mirror list — tried in order; first success wins.
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

SEARCH_RADIUS_M = 3000      # metres for POI counts
ROAD_RADIUS_M   = 1000      # metres for road density

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


def _overpass_query(query: str, timeout: int = 25) -> list[dict[str, Any]]:
    """Run an Overpass query with mirror fallback + one retry per mirror."""
    for url in OVERPASS_URLS:
        for attempt in range(2):           # 0 = first try, 1 = retry
            try:
                resp = requests.post(
                    url,
                    data={"data": query},
                    timeout=timeout,
                    headers={"Accept": "application/json"},
                )
                if resp.status_code == 429:
                    # rate-limited — wait and retry once, then next mirror
                    if attempt == 0:
                        time.sleep(2)
                        continue
                    break
                resp.raise_for_status()
                return resp.json().get("elements", [])
            except requests.exceptions.Timeout:
                logger.warning("Overpass timeout (%s, attempt %d)", url, attempt)
                break                       # skip retry on timeout, try next mirror
            except Exception as exc:
                logger.warning("Overpass error (%s, attempt %d): %s", url, attempt, exc)
                if attempt == 0:
                    time.sleep(1)
                    continue
                break
    return []


def _count_query(bbox: str, tag_filter: str, ql_timeout: int = 10) -> int:
    """Run a single bbox count query — lightest possible Overpass call.

    *tag_filter* is raw Overpass QL, e.g. ``["amenity"="hospital"]``.
    """
    query = (
        f"[out:json][timeout:{ql_timeout}];"
        f"node({bbox}){tag_filter};"
        f"out count;"
    )
    for el in _overpass_query(query, timeout=ql_timeout + 5):
        cnt = el.get("tags", {}).get("total")
        if cnt is not None:
            return int(cnt)
    return 0


# ---------------------------------------------------------------------------
# POI counts — one combined query (all categories, bbox, out count)
# ---------------------------------------------------------------------------

def _fetch_poi_counts(lat: float, lng: float) -> dict[str, int]:
    """All 4 POI categories + road count in a single Overpass request."""
    bb = _bbox(lat, lng, SEARCH_RADIUS_M)
    bb_road = _bbox(lat, lng, ROAD_RADIUS_M)

    # Single combined query — each group returns one 'count' element.
    # We use `make` to label each count so we can tell them apart.
    query = f"""
[out:json][timeout:20];
node({bb})["amenity"~"^(hospital|clinic)$"]->.hospitals;
node({bb})["amenity"~"^(school|college|university)$"]->.schools;
node({bb})["shop"~"^(mall|supermarket)$"]->.malls;
node({bb})["leisure"~"^(park|garden)$"]->.parks;
way({bb_road})["highway"~"^(motorway|trunk|primary|secondary|tertiary|residential)$"]->.roads;
.hospitals out count;
.schools out count;
.malls out count;
.parks out count;
.roads out count;
""".strip()

    elements = _overpass_query(query, timeout=25)

    # The API returns 5 count elements in the order we requested.
    counts = []
    for el in elements:
        total = el.get("tags", {}).get("total")
        if total is not None:
            counts.append(int(total))

    h = counts[0] if len(counts) > 0 else 0
    s = counts[1] if len(counts) > 1 else 0
    m = counts[2] if len(counts) > 2 else 0
    p = counts[3] if len(counts) > 3 else 0
    r = counts[4] if len(counts) > 4 else 0

    return {
        "hospital_count": h,
        "school_count": s,
        "mall_count": m,
        "park_count": p,
        "road_density": float(r),
    }


def _fetch_poi_counts_fallback(lat: float, lng: float) -> dict[str, int]:
    """Per-category fallback if the combined query fails."""
    bb = _bbox(lat, lng, SEARCH_RADIUS_M)
    bb_road = _bbox(lat, lng, ROAD_RADIUS_M)

    h = _count_query(bb, '["amenity"~"^(hospital|clinic)$"]')
    s = _count_query(bb, '["amenity"~"^(school|college|university)$"]')
    m = _count_query(bb, '["shop"~"^(mall|supermarket)$"]')
    p = _count_query(bb, '["leisure"~"^(park|garden)$"]')
    r = _count_query(bb_road,
                     '["highway"~"^(motorway|trunk|primary|secondary|tertiary|residential)$"]')

    return {
        "hospital_count": h,
        "school_count": s,
        "mall_count": m,
        "park_count": p,
        "road_density": float(r),
    }


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
    data = _fetch_poi_counts(lat_r, lng_r)
    # If combined query returned all zeros (likely failed), try fallback
    if all(v == 0 for v in data.values()):
        logger.info("Combined query empty — trying per-category fallback")
        data = _fetch_poi_counts_fallback(lat_r, lng_r)
    return data


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_locality_scores(address: str, lat: float | None = None,
                        lng: float | None = None) -> dict | None:
    """Return live locality scores for (lat, lng) using Overpass + hardcoded metro."""
    if lat is None or lng is None:
        return None

    try:
        # Round to ~110 m grid for caching
        lat_r = round(lat, 3)
        lng_r = round(lng, 3)

        # 1 Overpass request (cached)
        data = _cached_poi_counts(lat_r, lng_r)

        # Instant calculations (no API)
        metro_km = _nearest_metro_distance_km(lat, lng)
        it_hub_km = round(_haversine_km(lat, lng, _IT_HUB_LAT, _IT_HUB_LNG), 4)

        amenity = _amenity_score(
            data["hospital_count"], data["school_count"],
            data["mall_count"], data["park_count"],
        )
        connectivity = _connectivity_score(metro_km, data["road_density"])

        locality_name = address.strip().split(",")[0].strip() if address else "Selected Area"

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
            "road_density": data["road_density"],
            "match_method": "live_overpass",
        }
    except Exception as exc:
        logger.exception("Live locality scoring failed: %s", exc)
        return None
