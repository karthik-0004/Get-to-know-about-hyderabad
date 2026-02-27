"""
merge_master_dataset.py
Merges locality_features.csv, crime_scores.csv, and future_growth_scores.csv
into a single master_locality_data.csv.

Usage:
    python merge_master_dataset.py

Output: master_locality_data.csv with all features per locality.
"""

import logging
import os
import pandas as pd

# --- Configuration ---

INPUT_FILES = {
    "locality_features":     "locality_features.csv",
    "crime_scores":          "crime_scores.csv",
    "future_growth_scores":  "future_growth_scores.csv",
}

OUTPUT_FILE = "master_locality_data.csv"

# Columns to keep from each CSV (drops intermediate raw counts we don't need)
KEEP_COLUMNS = {
    "locality_features": [
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
        "amenity_score",
        "connectivity_score",
    ],
    "crime_scores": [
        "locality",
        "police_count",
        "industrial_count",
        "crime_score",
    ],
    "future_growth_scores": [
        "locality",
        "construction_count",
        "road_construction_count",
        "commercial_count",
        "metro_proximity_score",
        "it_proximity_score",
        "growth_score",
    ],
}


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def load_and_validate(key: str, path: str) -> pd.DataFrame:
    """Load a CSV, validate it exists and has expected columns, return cleaned df."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Required file not found: '{path}'")

    df = pd.read_csv(path)
    logging.info("Loaded %s — %d rows, %d cols", path, len(df), len(df.columns))

    # Drop duplicates
    before = len(df)
    df = df.drop_duplicates(subset="locality", keep="last").reset_index(drop=True)
    after = len(df)
    if before != after:
        logging.warning("Dropped %d duplicate locality rows from %s", before - after, path)

    # Keep only relevant columns (ignore missing optional ones gracefully)
    cols = [c for c in KEEP_COLUMNS[key] if c in df.columns]
    missing = set(KEEP_COLUMNS[key]) - set(cols)
    if missing:
        logging.warning("Columns missing from %s: %s", path, missing)

    return df[cols]


def main() -> None:
    setup_logging()
    logging.info("Starting master dataset merge ...")

    # --- Load all 3 CSVs ---
    dfs = {}
    for key, path in INPUT_FILES.items():
        try:
            dfs[key] = load_and_validate(key, path)
        except FileNotFoundError as e:
            logging.error(str(e))
            return

    base = dfs["locality_features"]
    crime = dfs["crime_scores"]
    growth = dfs["future_growth_scores"]

    # --- Merge on locality ---
    master = base.merge(crime,  on="locality", how="left")
    master = master.merge(growth, on="locality", how="left")

    # --- Report any localities that didn't match ---
    unmatched_crime  = master[master["crime_score"].isna()]["locality"].tolist()
    unmatched_growth = master[master["growth_score"].isna()]["locality"].tolist()

    if unmatched_crime:
        logging.warning(
            "%d localities missing crime_score: %s",
            len(unmatched_crime), unmatched_crime
        )
    if unmatched_growth:
        logging.warning(
            "%d localities missing growth_score: %s",
            len(unmatched_growth), unmatched_growth
        )

    # --- Fill any NaN scores with 5.0 (neutral midpoint) ---
    score_cols = ["crime_score", "growth_score", "amenity_score", "connectivity_score"]
    for col in score_cols:
        if col in master.columns:
            nulls = master[col].isna().sum()
            if nulls > 0:
                logging.warning("Filling %d nulls in '%s' with 5.0", nulls, col)
                master[col] = master[col].fillna(5.0)

    # --- Save ---
    master.to_csv(OUTPUT_FILE, index=False)
    logging.info(
        "Saved master dataset → %s  (%d rows × %d cols)",
        OUTPUT_FILE, len(master), len(master.columns)
    )

    # --- Summary ---
    print("\n=== Master Dataset Summary ===")
    print(f"Rows    : {len(master)}")
    print(f"Columns : {list(master.columns)}")
    print(f"\nScore ranges:")
    for col in score_cols:
        if col in master.columns:
            print(f"  {col:25s} min={master[col].min():.2f}  max={master[col].max():.2f}  mean={master[col].mean():.2f}")
    print(f"\nSaved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()