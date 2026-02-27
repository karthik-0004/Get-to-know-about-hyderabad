"""
future_growth_score.py
Generates future_growth_scores.csv with a growth_score (0-10) for each
Hyderabad locality, using OSM signals for development activity.

Usage:
    python future_growth_score.py

Crash-safe: appends one row per locality immediately after processing.
On restart, skips already-processed localities.

Reads locality coords directly from locality_features.csv — no re-geocoding.
"""

import logging
import math
import os
import time
from typing import Dict, List

import osmnx as ox
import pandas as pd

# --- Configuration ---

INPUT_FILE  = "locality_features.csv"
OUTPUT_FILE = "future_growth_scores.csv"
RADIUS_M    = 3000   # metres for all OSM queries

OUTPUT_COLUMNS = [
    "locality",
    "construction_count",
    "road_construction_count",
    "commercial_count",
    "metro_proximity_score",
    "it_proximity_score",
    "growth_score",
]

# --- Combined OSM tags for one-shot fetch ---

OSM_TAGS = {
    "building": ["construction"],
    "highway":  ["construction"],
    "office":   ["it"],
    "landuse":  ["commercial", "retail", "office"],
}


# --- Logging ---

def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# --- OSM fetch ---

def fetch_growth_signals(lat: float, lng: float) -> Dict[str, int]:
    """Fetch all growth-signal POIs in one OSM call. Returns counts per category."""
    counts = {
        "construction_count":      0,
        "road_construction_count": 0,
        "commercial_count":        0,
    }
    try:
        gdf = ox.features_from_point((lat, lng), tags=OSM_TAGS, dist=RADIUS_M)
        if gdf is None or gdf.empty:
            return counts

        if "building" in gdf.columns:
            counts["construction_count"] = int((gdf["building"] == "construction").sum())

        if "highway" in gdf.columns:
            counts["road_construction_count"] = int((gdf["highway"] == "construction").sum())

        if "office" in gdf.columns:
            it_offices = int((gdf["office"] == "it").sum())
        else:
            it_offices = 0

        if "landuse" in gdf.columns:
            commercial = int(gdf["landuse"].isin(["commercial", "retail", "office"]).sum())
        else:
            commercial = 0

        counts["commercial_count"] = it_offices + commercial

    except Exception as exc:
        logging.warning(
            "OSM fetch failed at (%.4f, %.4f): %s", lat, lng, exc
        )

    return counts


# --- Proximity score (inverted distance, 0-10) ---

def proximity_score(distance_km: float, max_km: float = 20.0) -> float:
    """Convert a distance in km to a 0-10 score. Closer = higher score."""
    if distance_km <= 0:
        return 10.0
    score = max(0.0, (max_km - distance_km) / max_km) * 10.0
    return round(score, 4)


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
        return pd.Series([out_max] * len(series), index=series.index, dtype="float64")
    return (series - lo) / (hi - lo) * (out_max - out_min) + out_min


# --- CSV helpers ---

def load_existing_output(path: str) -> pd.DataFrame:
    if os.path.isfile(path):
        try:
            df = pd.read_csv(path)
            logging.info("Loaded %d already-processed localities from %s", len(df), path)
            return df
        except Exception as exc:
            logging.warning("Could not read %s (%s) - starting fresh.", path, exc)
    return pd.DataFrame(columns=OUTPUT_COLUMNS)


def append_row(path: str, row: Dict) -> None:
    write_header = not os.path.isfile(path) or os.path.getsize(path) == 0
    pd.DataFrame([row], columns=OUTPUT_COLUMNS[:-1]).to_csv(
        path, mode="a", header=write_header, index=False
    )


# --- Normalisation pass ---

def normalise_scores() -> None:
    if not os.path.isfile(OUTPUT_FILE):
        logging.warning("No output file found - nothing to normalise.")
        return

    df = pd.read_csv(OUTPUT_FILE)
    if df.empty:
        logging.warning("CSV is empty - nothing to normalise.")
        return

    raw = (
        df["construction_count"]
        + df["road_construction_count"]
        + (df["commercial_count"] * 1.5)
        + df["metro_proximity_score"]
        + df["it_proximity_score"]
    )
    df["growth_score"] = min_max_scale(raw).round(4)
    df = df[OUTPUT_COLUMNS]
    df.to_csv(OUTPUT_FILE, index=False)
    logging.info(
        "Normalised growth_score for %d rows -> %s", len(df), OUTPUT_FILE
    )


# --- Main pipeline ---

def main() -> None:
    setup_logging()
    logging.info("Starting future growth score enrichment ...")

    # Load input coords from locality_features.csv
    if not os.path.isfile(INPUT_FILE):
        logging.error("Input file '%s' not found. Run locality_enrichment.py first.", INPUT_FILE)
        return

    input_df = pd.read_csv(INPUT_FILE)
    # Deduplicate in case of restart artifacts
    input_df = input_df.drop_duplicates(subset="locality", keep="last").reset_index(drop=True)
    logging.info("Loaded %d localities from %s", len(input_df), INPUT_FILE)

    # Determine already-processed
    existing_df = load_existing_output(OUTPUT_FILE)
    done_set = set(existing_df["locality"].tolist()) if not existing_df.empty else set()

    pending = input_df[~input_df["locality"].isin(done_set)]
    total = len(input_df)

    if pending.empty:
        logging.info("All localities already processed - running normalisation.")
        normalise_scores()
        return

    logging.info("%d / %d localities remaining. Starting enrichment ...", len(pending), total)

    for _, row in pending.iterrows():
        name = row["locality"]
        lat  = float(row["lat"])
        lng  = float(row["lng"])
        idx  = input_df.index[input_df["locality"] == name].tolist()[0] + 1

        print(f"[{idx}/{total}] Processing {name} ({lat:.4f}, {lng:.4f}) ...")

        signals = fetch_growth_signals(lat, lng)

        metro_score = proximity_score(float(row["metro_distance_km"]))
        it_score    = proximity_score(float(row["it_hub_distance_km"]))

        out_row = {
            "locality":               name,
            "construction_count":     signals["construction_count"],
            "road_construction_count": signals["road_construction_count"],
            "commercial_count":       signals["commercial_count"],
            "metro_proximity_score":  metro_score,
            "it_proximity_score":     it_score,
        }

        append_row(OUTPUT_FILE, out_row)
        logging.info("Saved %s to %s", name, OUTPUT_FILE)

    # Final normalisation pass once all rows are written
    normalise_scores()

    # Summary
    df = pd.read_csv(OUTPUT_FILE)
    logging.info("Done. Final CSV has %d rows.", len(df))
    print("\n" + df[["locality", "growth_score"]].to_string(index=False))


if __name__ == "__main__":
    main()