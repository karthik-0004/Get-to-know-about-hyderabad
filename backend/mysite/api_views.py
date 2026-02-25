import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .places_service import (
    SEARCH_RADIUS_METERS,
    PlacesAPIError,
    PlacesAuthError,
    PlacesNetworkError,
    PlacesServiceError,
    PlacesTimeoutError,
    analyze_area as fetch_nearby_places,
)


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

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    if not isinstance(payload, dict):
        return JsonResponse({"error": "JSON body must be an object"}, status=400)

    try:
        lat = _to_float(payload.get("lat"), "lat")
        lng = _to_float(payload.get("lng"), "lng")
        address = payload.get("address")

        if not isinstance(address, str) or not address.strip():
            raise ValueError("'address' must be a non-empty string")
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    try:
        places = fetch_nearby_places(lat=lat, lng=lng)
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

    return JsonResponse(
        {
            "area": address.strip(),
            "coordinates": {"lat": lat, "lng": lng},
            "radius_meters": SEARCH_RADIUS_METERS,
            **places,   # hospitals, malls, cinemas, schools, etc.
        },
        status=200,
    )