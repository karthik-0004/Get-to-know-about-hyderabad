"""
crime_score.py
Generates crime_scores.csv with a crime safety score (0–10, higher = safer)
for each Hyderabad locality in locality_features.csv.

Proxy signals from OpenStreetMap (via OSMnx):
  • police_count     — amenity=police within 3 km  (positive signal)
  • industrial_count — landuse=industrial within 3 km (negative signal)
  • highway_count    — highway=trunk within 3 km   (negative signal)

Scoring formula:
  raw = (police_count * 2) − industrial_count − (highway_count * 0.5)
  crime_score = min_max_normalize(raw, 0, 10)

Speed optimization:
  - Single combined OSM call per locality (was 3 separate calls)
  - Falls back to a broader tag set + 5000m radius if all counts are 0

Crash-safe: each row is appended to CSV immediately after processing.
On restart the script skips already-processed localities.

Usage:
    python crime_score.py
"""

import logging
import math
import os
from typing import Dict, List

import osmnx as ox
import pandas as pd

# --- Configuration ---

INPUT_FILE      = "locality_features.csv"
OUTPUT_FILE     = "crime_scores.csv"
SEARCH_RADIUS_M = 3000   # primary radius
FALLBACK_RADIUS_M = 5000 # fallback radius if all counts are 0

# Combined primary tags — one OSM call fetches everything
PRIMARY_TAGS = {
    "amenity": ["police"],
    "landuse": ["industrial"],
    "highway": ["trunk"],
}

RAW_COLUMNS: List[str] = [
    "locality",
    "police_count",
    "industrial_count",
    "highway_count",
]

FINAL_COLUMNS: List[str] = RAW_COLUMNS + ["crime_score"]


# --- Logging ---

def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# --- Min-max normalisation ---

def min_max_scale(
    series: pd.Series,
    out_min: float = 0.0,
    out_max: float = 10.0,
) -> pd.Series:
    if series.empty:
        return series
    lo, hi = float(series.min()), float(series.max())
    if math.isclose(lo, hi):
        return pd.Series(
            [out_max] * len(series), index=series.index, dtype="float64"
        )
    return (series - lo) / (hi - lo) * (out_max - out_min) + out_min


# --- Single combined OSM fetch ---

def fetch_crime_signals(lat: float, lng: float) -> Dict[str, int]:
    """
    Fetch all crime-signal POIs in ONE OSM call.
    If all counts are 0, retries once with a larger radius.
    Returns dict: police_count, industrial_count, highway_count.
    """

    def _parse(gdf) -> Dict[str, int]:
        counts = {"police_count": 0, "industrial_count": 0, "highway_count": 0}
        if gdf is None or gdf.empty:
            return counts
        if "amenity" in gdf.columns:
            counts["police_count"] = int((gdf["amenity"] == "police").sum())
        if "landuse" in gdf.columns:
            counts["industrial_count"] = int((gdf["landuse"] == "industrial").sum())
        if "highway" in gdf.columns:
            counts["highway_count"] = int((gdf["highway"] == "trunk").sum())
        return counts

    def _fetch(radius: int) -> Dict[str, int]:
        try:
            gdf = ox.features_from_point((lat, lng), tags=PRIMARY_TAGS, dist=radius)
            return _parse(gdf)
        except Exception as exc:
            logging.warning(
                "OSM fetch failed at (%.4f, %.4f) radius=%dm: %s",
                lat, lng, radius, exc,
            )
            return {"police_count": 0, "industrial_count": 0, "highway_count": 0}

    # Stage 1: primary radius
    counts = _fetch(SEARCH_RADIUS_M)

    # Stage 2: fallback to larger radius only if everything is 0
    if all(v == 0 for v in counts.values()):
        logging.info("  All zero at %dm — retrying at %dm ...", SEARCH_RADIUS_M, FALLBACK_RADIUS_M)
        counts = _fetch(FALLBACK_RADIUS_M)

    return counts


# --- CSV helpers ---

def load_existing_csv(path: str) -> pd.DataFrame:
    if os.path.isfile(path):
        try:
            df = pd.read_csv(path)
            logging.info("Loaded %d already-processed localities from %s", len(df), path)
            return df
        except Exception as exc:
            logging.warning("Could not read %s (%s) - starting fresh.", path, exc)
    return pd.DataFrame(columns=RAW_COLUMNS)


def append_row_to_csv(path: str, row: Dict[str, object]) -> None:
    write_header = not os.path.isfile(path) or os.path.getsize(path) == 0
    pd.DataFrame([row], columns=RAW_COLUMNS).to_csv(
        path, mode="a", header=write_header, index=False
    )


# --- Main pipeline ---

def process_localities() -> None:
    if not os.path.isfile(INPUT_FILE):
        logging.error("Input file %s not found. Run locality_enrichment.py first.", INPUT_FILE)
        return

    source_df = pd.read_csv(INPUT_FILE)
    source_df = source_df.drop_duplicates(subset="locality", keep="last").reset_index(drop=True)
    logging.info("Loaded %d localities from %s", len(source_df), INPUT_FILE)

    existing_df = load_existing_csv(OUTPUT_FILE)
    done_set = set(existing_df["locality"].tolist()) if not existing_df.empty else set()

    total = len(source_df)
    pending = source_df[~source_df["locality"].isin(done_set)]

    if pending.empty:
        logging.info("All %d localities already processed - nothing to do.", total)
        return

    logging.info("%d / %d localities remaining ...", len(pending), total)

    for _, src_row in pending.iterrows():
        name = src_row["locality"]
        lat  = float(src_row["lat"])
        lng  = float(src_row["lng"])
        idx  = source_df.index[source_df["locality"] == name].tolist()[0] + 1

        print(f"[{idx}/{total}] Processing {name} ({lat:.4f}, {lng:.4f}) ...")

        counts = fetch_crime_signals(lat, lng)

        row: Dict[str, object] = {
            "locality":         name,
            "police_count":     counts["police_count"],
            "industrial_count": counts["industrial_count"],
            "highway_count":    counts["highway_count"],
        }

        append_row_to_csv(OUTPUT_FILE, row)
        logging.info(
            "  Saved %s  police=%d  industrial=%d  highway=%d",
            name, counts["police_count"], counts["industrial_count"], counts["highway_count"],
        )


def normalise_scores() -> None:
    if not os.path.isfile(OUTPUT_FILE):
        logging.warning("No output file found - nothing to normalise.")
        return

    df = pd.read_csv(OUTPUT_FILE)
    if df.empty:
        logging.warning("CSV is empty - nothing to normalise.")
        return

    raw = (
        df["police_count"] * 2
        - df["industrial_count"]
        - df["highway_count"] * 0.5
    )
    df["crime_score"] = min_max_scale(raw, 0.0, 10.0).round(4)
    df = df[FINAL_COLUMNS]
    df.to_csv(OUTPUT_FILE, index=False)
    logging.info("Normalised crime_score for %d rows -> %s", len(df), OUTPUT_FILE)


def main() -> None:
    setup_logging()
    logging.info("Starting crime-score enrichment for Hyderabad ...")
    process_localities()
    normalise_scores()

    if os.path.isfile(OUTPUT_FILE):
        df = pd.read_csv(OUTPUT_FILE)
        logging.info("Final CSV has %d rows.", len(df))
        print("\n" + df.to_string(index=False))


if __name__ == "__main__":
    main()