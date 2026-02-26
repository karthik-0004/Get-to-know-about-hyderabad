"""
locality_enrichment.py
Enriches Hyderabad localities with OSMnx / geopy features and saves
results incrementally to locality_features.csv.

Usage:
    python locality_enrichment.py

Crash-safe: each locality row is appended to CSV immediately after
processing.  On restart the script reads the existing CSV and skips
already-processed localities.

Speed optimizations:
  - Single OSM call fetches ALL POI types at once, results split by tag.
  - Fallback: if any category is 0, one retry with broader tags + 3000m radius.
  - GEOCODE_SLEEP reduced to 1.0s (Nominatim rate limit is 1 req/s).
"""

import logging
import math
import os
import time
from collections import OrderedDict
from typing import Dict, List, Optional, Sequence, Tuple

import osmnx as ox
import pandas as pd
from geopy.geocoders import Nominatim

# --- Configuration ---

OUTPUT_FILE = "locality_features.csv"
GEOCODE_SLEEP = 1.0        # seconds between Nominatim calls (rate limit is 1 req/s)
FEATURE_RADIUS_M = 2000    # metres for POI queries (primary)
FALLBACK_RADIUS_M = 3000   # metres for fallback POI queries
ROAD_RADIUS_M = 1000       # metres for road-density graph

# --- Combined POI tags: one OSM call fetches everything ---
# Primary: tighter/more reliable tags
PRIMARY_TAGS = {
    "amenity": ["hospital", "school"],
    "shop":    ["mall", "supermarket"],
    "leisure": ["park"],
}

# Fallback: broader tags used if any category returned 0
FALLBACK_TAGS = {
    "amenity": ["hospital", "clinic", "doctors", "health_post",
                "school", "college", "university", "kindergarten"],
    "shop":    ["mall", "supermarket", "convenience", "department_store", "wholesale"],
    "leisure": ["park", "garden", "nature_reserve", "recreation_ground"],
}

# Map each tag value → POI bucket
HOSPITAL_TAGS = {"hospital", "clinic", "doctors", "health_post"}
SCHOOL_TAGS   = {"school", "college", "university", "kindergarten"}
MALL_TAGS     = {"mall", "supermarket", "convenience", "department_store", "wholesale"}
PARK_TAGS     = {"park", "garden", "nature_reserve", "recreation_ground"}

# --- Locality name -> Nominatim query ---

LOCALITY_QUERIES: OrderedDict = OrderedDict([
    ("Gachibowli",          "Gachibowli, Hyderabad, India"),
    ("Madhapur",            "Madhapur, Hyderabad, India"),
    ("Kondapur",            "Kondapur, Hyderabad, India"),
    ("Banjara Hills",       "Banjara Hills, Hyderabad, India"),
    ("Jubilee Hills",       "Jubilee Hills, Hyderabad, India"),
    ("Hitech City",         "Hitech City, Hyderabad, India"),
    ("Kukatpally",          "Kukatpally, Hyderabad, India"),
    ("Miyapur",             "Miyapur, Hyderabad, India"),
    ("Manikonda",           "Manikonda, Hyderabad, India"),
    ("Nallagandla",         "Nallagandla, Hyderabad, India"),
    ("Tellapur",            "Tellapur, Hyderabad, India"),
    ("Narsingi",            "Narsingi, Rangareddy, Telangana, India"),
    ("Kokapet",             "Kokapet, Hyderabad, India"),
    ("Financial District",  "Financial District, Nanakramguda, Hyderabad, India"),
    ("Nanakramguda",        "Nanakramguda, Hyderabad, India"),
    ("Begumpet",            "Begumpet, Hyderabad, India"),
    ("Ameerpet",            "Ameerpet, Hyderabad, India"),
    ("SR Nagar",            "SR Nagar, Hyderabad, India"),
    ("Balkampet",           "Balkampet, Hyderabad, India"),
    ("Moosapet",            "Moosapet, Hyderabad, India"),
    ("Bowenpally",          "Bowenpally, Hyderabad, India"),
    ("Secunderabad",        "Secunderabad, Telangana, India"),
    ("Tarnaka",             "Tarnaka, Hyderabad, India"),
    ("Malkajgiri",          "Malkajgiri, Hyderabad, India"),
    ("Uppal",               "Uppal, Hyderabad, India"),
    ("Nagole",              "Nagole, Hyderabad, India"),
    ("LB Nagar",            "LB Nagar, Hyderabad, India"),
    ("Dilsukhnagar",        "Dilsukhnagar, Hyderabad, India"),
    ("Vanasthalipuram",     "Vanasthalipuram, Hyderabad, India"),
    ("Hayathnagar",         "Hayathnagar, Hyderabad, India"),
    ("Sainikpuri",          "Sainikpuri, Hyderabad, India"),
    ("Alwal",               "Alwal, Hyderabad, India"),
    ("Kompally",            "Kompally, Hyderabad, India"),
    ("Medchal",             "Medchal, Telangana, India"),
    ("Shamirpet",           "Shamirpet, Medchal, Telangana, India"),
    ("Bachupally",          "Bachupally, Hyderabad, India"),
    ("Nizampet",            "Nizampet, Hyderabad, India"),
    ("Pragathi Nagar",      "Pragathi Nagar, Kukatpally, Hyderabad, India"),
    ("Chandanagar",         "Chandanagar, Hyderabad, India"),
    ("Mokila",              "Mokila, Rangareddy, Telangana, India"),
    ("Shankarpally",        "Shankarpally, Rangareddy, Telangana, India"),
    ("Rajendra Nagar",      "Rajendra Nagar, Hyderabad, India"),
    ("Attapur",             "Attapur, Hyderabad, India"),
    ("Mehdipatnam",         "Mehdipatnam, Hyderabad, India"),
    ("Tolichowki",          "Tolichowki, Hyderabad, India"),
    ("Masab Tank",          "Masab Tank, Hyderabad, India"),
    ("Khairatabad",         "Khairatabad, Hyderabad, India"),
    ("Somajiguda",          "Somajiguda, Hyderabad, India"),
    ("Punjagutta",          "Punjagutta, Hyderabad, India"),
    ("Himayatnagar",        "Himayatnagar, Hyderabad, India"),
    ("Shamshabad",          "Shamshabad, Rangareddy, Telangana, India"),
    ("Adibatla",            "Adibatla, Rangareddy, Telangana, India"),
    ("Boduppal",            "Boduppal, Hyderabad, India"),
    ("Ghatkesar",           "Ghatkesar, Medchal, Telangana, India"),
    ("Peerzadiguda",        "Peerzadiguda, Hyderabad, India"),
    ("Nacharam",            "Nacharam, Hyderabad, India"),
    ("Habsiguda",           "Habsiguda, Hyderabad, India"),
    ("Moula Ali",           "Moula Ali, Hyderabad, India"),
    ("Charminar",           "Charminar, Hyderabad, India"),
    ("Falaknuma",           "Falaknuma, Hyderabad, India"),
    ("Yapral",              "Yapral, Hyderabad, India"),
    ("Bandlaguda",          "Bandlaguda, Hyderabad, India"),
    ("Kothapet",            "Kothapet, Hyderabad, India"),
    ("Suchitra",            "Suchitra, Hyderabad, India"),
    ("ECIL",                "ECIL, Hyderabad, India"),
    ("Balanagar",           "Balanagar, Hyderabad, India"),
    ("Suraram",             "Suraram, Hyderabad, India"),
    ("AS Rao Nagar",        "AS Rao Nagar, Hyderabad, India"),
    ("Kapra",               "Kapra, Hyderabad, India"),
    ("Amberpet",            "Amberpet, Hyderabad, India"),
    ("Nampally",            "Nampally, Hyderabad, India"),
    ("Abids",               "Abids, Hyderabad, India"),
    ("Himayatsagar",        "Himayatsagar, Hyderabad, India"),
    ("Patancheru",          "Patancheru, Sangareddy, Telangana, India"),
    ("Isnapur",             "Isnapur, Sangareddy, Telangana, India"),
    ("Toopran",             "Toopran, Medak, Telangana, India"),
    ("Sadashivpet",         "Sadashivpet, Sangareddy, Telangana, India"),
    ("Zaheerabad",          "Zaheerabad, Sangareddy, Telangana, India"),
    ("Tandur",              "Tandur, Rangareddy, Telangana, India"),
    ("Vikarabad",           "Vikarabad, Telangana, India"),
    ("Chevella",            "Chevella, Rangareddy, Telangana, India"),
    ("Ibrahimpatnam",       "Ibrahimpatnam, Rangareddy, Telangana, India"),
    ("Nagaram",             "Nagaram, Hyderabad, India"),
    ("Dammaiguda",          "Dammaiguda, Hyderabad, India"),
    ("Dundigal",            "Dundigal, Hyderabad, India"),
    ("Quthbullapur",        "Quthbullapur, Hyderabad, India"),
    ("Jeedimetla",          "Jeedimetla, Hyderabad, India"),
    ("Bahadurpura",         "Bahadurpura, Hyderabad, India"),
    ("Santoshnagar",        "Santoshnagar, Hyderabad, India"),
    ("Karmanghat",          "Karmanghat, Hyderabad, India"),
    ("Saroornagar",         "Saroornagar, Hyderabad, India"),
    ("Meerpet",             "Meerpet, Hyderabad, India"),
    ("Badangpet",           "Badangpet, Hyderabad, India"),
    ("Balapur",             "Balapur, Hyderabad, India"),
    ("Turkayamjal",         "Turkayamjal, Rangareddy, Telangana, India"),
    # --- Appended ---
    ("Musheerabad",         "Musheerabad, Hyderabad, India"),
    ("RTC X Roads",         "RTC X Roads, Hyderabad, India"),
    ("Gandhi Nagar",        "Gandhi Nagar, Hyderabad, India"),
    ("Koti",                "Koti, Hyderabad, India"),
    ("Sultan Bazar",        "Sultan Bazar, Hyderabad, India"),
    ("King Koti",           "King Koti, Hyderabad, India"),
    ("Troop Bazar",         "Troop Bazar, Hyderabad, India"),
    ("Chirag Ali Lane",     "Chirag Ali Lane, Hyderabad, India"),
    ("Narayanguda",         "Narayanguda, Hyderabad, India"),
    ("Vidyanagar",          "Vidyanagar, Hyderabad, India"),
    ("Domalguda",           "Domalguda, Hyderabad, India"),
    ("Goshamahal",          "Goshamahal, Hyderabad, India"),
    ("Barkatpura",          "Barkatpura, Hyderabad, India"),
    ("Greenlands",          "Greenlands, Hyderabad, India"),
    ("Liberty",             "Liberty, Hyderabad, India"),
    ("Padmarao Nagar",      "Padmarao Nagar, Hyderabad, India"),
    ("Marredpally",         "Marredpally, Secunderabad, Telangana, India"),
    ("West Marredpally",    "West Marredpally, Secunderabad, Telangana, India"),
    ("Chilkalguda",         "Chilkalguda, Hyderabad, India"),
    ("Trimulgherry",        "Trimulgherry, Secunderabad, Telangana, India"),
    ("Tilaknagar",          "Tilaknagar, Hyderabad, India"),
    ("Karkhana",            "Karkhana, Secunderabad, Telangana, India"),
    ("SD Road",             "SD Road, Secunderabad, Telangana, India"),
    ("Paradise",            "Paradise, Secunderabad, Telangana, India"),
    ("Rasoolpura",          "Rasoolpura, Secunderabad, Telangana, India"),
    ("Bolarum",             "Bolarum, Secunderabad, Telangana, India"),
    ("Regimental Bazar",    "Regimental Bazar, Secunderabad, Telangana, India"),
    ("Lalapet",             "Lalapet, Hyderabad, India"),
    ("Ramanthapur",         "Ramanthapur, Hyderabad, India"),
    ("Tukaram Gate",        "Tukaram Gate, Hyderabad, India"),
    ("Mallapur",            "Mallapur, Hyderabad, India"),

])

# --- Hardcoded reference coordinates ---

IT_HUB_COORDS: List[Tuple[float, float]] = [
    (17.4435, 78.3772),   # Hitec City
    (17.4401, 78.3489),   # Gachibowli
    (17.4504, 78.3854),   # Madhapur
    (17.4600, 78.3548),   # Kondapur
]

METRO_STATION_COORDS: List[Tuple[float, float]] = [
    # Red Line (Miyapur - LB Nagar)
    (17.4969, 78.3478),   # Miyapur
    (17.4932, 78.3572),   # JNTU College
    (17.4893, 78.3637),   # KPHB Colony
    (17.4849, 78.3716),   # Kukatpally
    (17.4813, 78.3796),   # Balanagar
    (17.4734, 78.3891),   # Moosapet
    (17.4686, 78.3949),   # Bharat Nagar
    (17.4615, 78.4040),   # Erragadda
    (17.4554, 78.4111),   # ESI Hospital
    (17.4499, 78.4169),   # SR Nagar
    (17.4375, 78.4484),   # Ameerpet
    (17.4276, 78.4505),   # Punjagutta
    (17.4210, 78.4534),   # Irrum Manzil
    (17.4164, 78.4557),   # Khairatabad
    (17.4089, 78.4616),   # Lakdikapul
    (17.4043, 78.4680),   # Assembly
    (17.3961, 78.4720),   # Nampally
    (17.3895, 78.4760),   # Gandhi Bhavan
    (17.3830, 78.4783),   # Osmania Medical College
    (17.3780, 78.4808),   # MG Bus Station
    (17.3700, 78.4900),   # Malakpet
    (17.3648, 78.4963),   # New Market
    (17.3590, 78.5020),   # Musarambagh
    (17.3522, 78.5098),   # Dilsukhnagar
    (17.3460, 78.5178),   # Chaitanyapuri
    (17.3400, 78.5263),   # Victoria Memorial
    (17.3370, 78.5342),   # LB Nagar
    # Blue Line (Raidurg - Nagole)
    (17.4260, 78.3840),   # Raidurg
    (17.4435, 78.3830),   # Hitec City
    (17.4380, 78.3920),   # Durgam Cheruvu
    (17.4448, 78.3948),   # Madhapur
    (17.4403, 78.4080),   # Peddamma Gudi
    (17.4310, 78.4150),   # Jubilee Hills Check Post
    (17.4290, 78.4260),   # Road No 5 Jubilee Hills
    (17.4327, 78.4355),   # Yusufguda
    (17.4390, 78.4415),   # Madhura Nagar
    # Green Line (JBS - MGBS via Parade Ground)
    (17.4430, 78.4630),   # Begumpet
    (17.4487, 78.4546),   # Prakash Nagar
    (17.4540, 78.4595),   # Rasoolpura
    (17.4619, 78.4712),   # Paradise
    (17.4636, 78.4768),   # Parade Ground
    (17.4383, 78.5013),   # Secunderabad East
    (17.4336, 78.5081),   # Mettuguda
    (17.4264, 78.5196),   # Tarnaka
    (17.4119, 78.5366),   # Habsiguda
    (17.4076, 78.5470),   # NGRI
    (17.4033, 78.5549),   # Stadium
    (17.4005, 78.5596),   # Uppal
    (17.3945, 78.5632),   # Nagole
]

# Columns written to CSV during per-locality append (no scores yet)
RAW_COLUMNS: List[str] = [
    "locality",
    "lat",
    "lng",
    "metro_distance_km",
    "it_hub_distance_km",
    "hospital_count",
    "school_count",
    "mall_count",
    "park_count",
    "road_density",
]

# Final columns after normalisation pass
OUTPUT_COLUMNS: List[str] = RAW_COLUMNS + [
    "amenity_score",
    "connectivity_score",
]


# --- Helpers ---

def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two points in kilometres."""
    R = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def nearest_distance_km(
    lat: float,
    lng: float,
    targets: Sequence[Tuple[float, float]],
) -> float:
    """Return distance (km) from (lat, lng) to the closest target point."""
    if not targets:
        return 0.0
    return round(min(haversine_km(lat, lng, t[0], t[1]) for t in targets), 4)


def geocode_locality(
    geolocator: Nominatim,
    name: str,
    primary_query: str,
) -> Optional[Tuple[float, float]]:
    """
    Try geocoding with *primary_query*.  If that fails, retry with the
    fallback query "<name>, Telangana, India".
    Returns (lat, lng) or None.
    """
    for attempt, query in enumerate(
        [primary_query, f"{name}, Telangana, India"], start=1
    ):
        try:
            loc = geolocator.geocode(query, exactly_one=True, timeout=30)
        except Exception as exc:
            logging.warning("Geocode attempt %d failed for '%s': %s", attempt, query, exc)
            loc = None

        if loc is not None:
            return float(loc.latitude), float(loc.longitude)

        logging.warning("Geocode attempt %d returned nothing for '%s'", attempt, query)

        if attempt == 1:
            time.sleep(GEOCODE_SLEEP)

    return None


def fetch_all_poi_counts(
    lat: float,
    lng: float,
) -> Dict[str, int]:
    """
    Fetch counts for all POI categories in ONE OSM call.
    If any category is 0, fires ONE fallback call with broader tags + 3000m radius.
    Returns dict with keys: hospital, school, mall, park.
    """

    def _parse_gdf(gdf) -> Dict[str, int]:
        counts = {"hospital": 0, "school": 0, "mall": 0, "park": 0}
        if gdf is None or gdf.empty:
            return counts
        for col, tag_set, key in [
            ("amenity", HOSPITAL_TAGS, "hospital"),
            ("amenity", SCHOOL_TAGS,   "school"),
            ("shop",    MALL_TAGS,     "mall"),
            ("leisure", PARK_TAGS,     "park"),
        ]:
            if col in gdf.columns:
                counts[key] = int(gdf[col].isin(tag_set).sum())
        return counts

    def _fetch(tags, radius) -> Dict[str, int]:
        try:
            gdf = ox.features_from_point((lat, lng), tags=tags, dist=radius)
            return _parse_gdf(gdf)
        except Exception as exc:
            logging.warning(
                "OSM combined fetch failed at (%.4f, %.4f) radius=%dm: %s",
                lat, lng, radius, exc,
            )
            return {"hospital": 0, "school": 0, "mall": 0, "park": 0}

    # Stage 1: primary tags, 2000m
    counts = _fetch(PRIMARY_TAGS, FEATURE_RADIUS_M)

    # Stage 2: if anything is 0, retry once with broader tags + 3000m
    if any(v == 0 for v in counts.values()):
        fallback = _fetch(FALLBACK_TAGS, FALLBACK_RADIUS_M)
        # Only upgrade zeros — don't overwrite non-zero primary results
        for key in counts:
            if counts[key] == 0 and fallback[key] > 0:
                logging.info("  [%s] Recovered %d via fallback.", key, fallback[key])
                counts[key] = fallback[key]

    return counts


def safe_road_density(lat: float, lng: float, radius_m: int = ROAD_RADIUS_M) -> int:
    """Number of road (drive) edges within *radius_m*.  Returns 0 on error."""
    try:
        G = ox.graph_from_point(
            (lat, lng),
            dist=radius_m,
            network_type="drive",
            simplify=True,
        )
        if G is None:
            return 0
        return int(G.number_of_edges())
    except Exception as exc:
        logging.warning("Road network fetch failed at (%.4f, %.4f): %s", lat, lng, exc)
        return 0


def min_max_scale(
    series: pd.Series,
    out_min: float = 0.0,
    out_max: float = 10.0,
) -> pd.Series:
    """Min-max normalise *series* into [out_min, out_max]."""
    if series.empty:
        return series
    lo, hi = float(series.min()), float(series.max())
    if math.isclose(lo, hi):
        return pd.Series([out_max] * len(series), index=series.index, dtype="float64")
    return (series - lo) / (hi - lo) * (out_max - out_min) + out_min


# --- CSV helpers (incremental save) ---

def load_existing_csv(path: str) -> pd.DataFrame:
    """Load already-processed rows, or return an empty DataFrame."""
    if os.path.isfile(path):
        try:
            df = pd.read_csv(path)
            logging.info("Loaded %d already-processed localities from %s", len(df), path)
            return df
        except Exception as exc:
            logging.warning("Could not read existing %s (%s) - starting fresh.", path, exc)
    return pd.DataFrame(columns=RAW_COLUMNS)


def append_row_to_csv(path: str, row: Dict[str, object]) -> None:
    """Append a single row dict to the CSV file (create with header if needed)."""
    write_header = not os.path.isfile(path) or os.path.getsize(path) == 0
    df_row = pd.DataFrame([row], columns=RAW_COLUMNS)
    df_row.to_csv(path, mode="a", header=write_header, index=False)


# --- Main pipeline ---

def process_localities() -> None:
    """Iterate over localities, geocode + fetch OSM features, save incrementally."""
    geolocator = Nominatim(user_agent="hyderabad_locality_enrichment")

    # 1. Determine which localities are already done
    existing_df = load_existing_csv(OUTPUT_FILE)
    done_set = set(existing_df["locality"].tolist()) if not existing_df.empty else set()

    all_names = list(LOCALITY_QUERIES.keys())
    total = len(all_names)
    pending = [n for n in all_names if n not in done_set]

    if not pending:
        logging.info("All %d localities already processed - nothing to do.", total)
        return

    logging.info(
        "%d / %d localities remaining. Starting enrichment ...",
        len(pending), total,
    )

    for name in pending:
        idx = all_names.index(name) + 1
        print(f"[{idx}/{total}] Processing {name}...")

        primary_query = LOCALITY_QUERIES[name]
        coords = geocode_locality(geolocator, name, primary_query)
        time.sleep(GEOCODE_SLEEP)

        if coords is None:
            logging.warning("Skipping %s - geocoding failed.", name)
            continue

        lat, lng = coords

        # Distance features
        metro_dist = nearest_distance_km(lat, lng, METRO_STATION_COORDS)
        it_hub_dist = nearest_distance_km(lat, lng, IT_HUB_COORDS)

        # POI counts — single OSM call with fallback
        poi = fetch_all_poi_counts(lat, lng)
        hospitals = poi["hospital"]
        schools   = poi["school"]
        malls     = poi["mall"]
        parks     = poi["park"]

        # Road density (1 km radius)
        roads = safe_road_density(lat, lng, ROAD_RADIUS_M)

        row: Dict[str, object] = {
            "locality":            name,
            "lat":                 round(lat, 6),
            "lng":                 round(lng, 6),
            "metro_distance_km":   metro_dist,
            "it_hub_distance_km":  it_hub_dist,
            "hospital_count":      hospitals,
            "school_count":        schools,
            "mall_count":          malls,
            "park_count":          parks,
            "road_density":        roads,
        }

        # Append immediately so nothing is lost on crash
        append_row_to_csv(OUTPUT_FILE, row)
        logging.info("Saved %s to %s", name, OUTPUT_FILE)


def normalise_scores() -> None:
    """
    Read the full CSV, compute amenity_score and connectivity_score via
    min-max normalisation (0-10), and overwrite the file with final columns.
    """
    if not os.path.isfile(OUTPUT_FILE):
        logging.warning("No output file found - nothing to normalise.")
        return

    df = pd.read_csv(OUTPUT_FILE)

    if df.empty:
        logging.warning("CSV is empty - nothing to normalise.")
        return

    amenity_raw = (
        df["hospital_count"]
        + df["school_count"]
        + df["mall_count"]
        + df["park_count"]
    )
    df["amenity_score"]      = min_max_scale(amenity_raw).round(4)
    df["connectivity_score"] = min_max_scale(df["road_density"]).round(4)

    df = df[OUTPUT_COLUMNS]
    df.to_csv(OUTPUT_FILE, index=False)
    logging.info(
        "Normalised amenity_score & connectivity_score for %d rows -> %s",
        len(df), OUTPUT_FILE,
    )


# --- Entry point ---

def main() -> None:
    setup_logging()
    logging.info("Starting locality enrichment for Hyderabad ...")

    process_localities()
    normalise_scores()

    # Print summary
    if os.path.isfile(OUTPUT_FILE):
        df = pd.read_csv(OUTPUT_FILE)
        logging.info("Final CSV has %d rows.", len(df))
        print("\n" + df.to_string(index=False))


if __name__ == "__main__":
    main()