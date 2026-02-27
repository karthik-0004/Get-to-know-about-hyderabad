"""
Locality enrichment service — loads locality_features.csv once at import
time and exposes get_locality_scores(address) for fuzzy-match lookup.
"""

import csv
import logging
from difflib import get_close_matches
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load locality data once at module import
# ---------------------------------------------------------------------------
_CSV_PATH: Path = settings.ML_MODEL_DIR / "locality_features.csv"

_LOCALITY_DATA: dict[str, dict] = {}   # locality_name_lower → row dict
_LOCALITY_NAMES: list[str] = []        # original-case names for display

_SCORE_FIELDS = [
    "amenity_score",
    "connectivity_score",
    "metro_distance_km",
    "it_hub_distance_km",
    "hospital_count",
    "school_count",
    "mall_count",
    "park_count",
    "road_density",
]

try:
    with open(_CSV_PATH, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            name = row["locality"].strip()
            _LOCALITY_NAMES.append(name)
            _LOCALITY_DATA[name.lower()] = {
                "locality": name,
                **{field: float(row[field]) for field in _SCORE_FIELDS},
            }
    logger.info(
        "Loaded %d localities from %s", len(_LOCALITY_DATA), _CSV_PATH
    )
except FileNotFoundError:
    logger.warning("locality_features.csv not found at %s", _CSV_PATH)
except Exception as exc:
    logger.exception("Failed to load locality_features.csv: %s", exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_locality_scores(address: str) -> dict | None:
    """Return enrichment scores for the locality best-matching *address*.

    Uses difflib.get_close_matches for fuzzy matching against known locality
    names.  Returns ``None`` when no reasonable match is found.
    """
    if not _LOCALITY_DATA:
        return None

    if not address:
        return None

    # Normalise the incoming address to lowercase for matching
    addr_lower = address.lower()

    # 1. Exact substring match — check if any known locality name appears
    #    inside the address string (most reliable).
    for name_lower, data in _LOCALITY_DATA.items():
        if name_lower in addr_lower:
            return {**data, "match_method": "substring"}

    # 2. Token-level fuzzy match — split the address into words and try to
    #    match individual tokens against locality names.
    addr_tokens = addr_lower.replace(",", " ").split()
    lower_names = list(_LOCALITY_DATA.keys())

    for token in addr_tokens:
        matches = get_close_matches(token, lower_names, n=1, cutoff=0.75)
        if matches:
            return {**_LOCALITY_DATA[matches[0]], "match_method": "fuzzy"}

    # 3. Whole-address fuzzy match (last resort)
    matches = get_close_matches(addr_lower, lower_names, n=1, cutoff=0.5)
    if matches:
        return {**_LOCALITY_DATA[matches[0]], "match_method": "fuzzy"}

    return None
