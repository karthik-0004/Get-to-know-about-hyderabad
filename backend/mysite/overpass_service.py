from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


OVERPASS_URL = "https://overpass-api.de/api/interpreter"
SEARCH_RADIUS_METERS = 3000


class OverpassServiceError(Exception):
    pass


class OverpassTimeoutError(OverpassServiceError):
    pass


class OverpassNetworkError(OverpassServiceError):
    pass


@dataclass(frozen=True)
class AreaSummary:
    hospitals: int
    police_stations: int
    malls: int
    industrial_areas: int
    parks: int


def _build_overpass_query(lat: float, lng: float, radius_meters: int) -> str:
    return f"""
[out:json][timeout:25];
(
  nwr(around:{radius_meters},{lat},{lng})[amenity=hospital];
  nwr(around:{radius_meters},{lat},{lng})[amenity=police];
  nwr(around:{radius_meters},{lat},{lng})[shop=mall];
  nwr(around:{radius_meters},{lat},{lng})[amenity=marketplace];
  nwr(around:{radius_meters},{lat},{lng})[landuse=industrial];
  nwr(around:{radius_meters},{lat},{lng})[leisure=park];
);
out body;
""".strip()


def _count_categories(elements: list[dict[str, Any]]) -> AreaSummary:
    hospitals = 0
    police_stations = 0
    malls = 0
    industrial_areas = 0
    parks = 0

    for element in elements:
        tags = element.get("tags", {})
        if tags.get("amenity") == "hospital":
            hospitals += 1
        if tags.get("amenity") == "police":
            police_stations += 1
        if tags.get("shop") == "mall" or tags.get("amenity") == "marketplace":
            malls += 1
        if tags.get("landuse") == "industrial":
            industrial_areas += 1
        if tags.get("leisure") == "park":
            parks += 1

    return AreaSummary(
        hospitals=hospitals,
        police_stations=police_stations,
        malls=malls,
        industrial_areas=industrial_areas,
        parks=parks,
    )


def analyze_nearby_location(lat: float, lng: float, radius_meters: int = SEARCH_RADIUS_METERS) -> AreaSummary:
    query = _build_overpass_query(lat=lat, lng=lng, radius_meters=radius_meters)

    try:
        response = requests.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=35,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
    except requests.exceptions.Timeout as exc:
        raise OverpassTimeoutError("Overpass request timed out") from exc
    except requests.exceptions.RequestException as exc:
        raise OverpassNetworkError("Failed to reach Overpass API") from exc

    payload = response.json()
    elements = payload.get("elements", [])

    return _count_categories(elements)