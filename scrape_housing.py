"""
scrape_housing.py
Selenium scraper for housing.com Hyderabad real-estate listings.

Usage:
    python scrape_housing.py

Features:
  - Attempts all 126 localities with name-variant fallback.
  - Saves rows to CSV after every locality (crash-safe).
  - Resumes from where it left off on restart.
  - Multi-page pagination (up to MAX_PAGES per locality).
  - Anti-bot stealth options for Chrome.
"""

import csv
import os
import random
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

OUTPUT_FILE = "housing_hyderabad.csv"
SOURCE_NAME = "Housing.com"
MAX_PAGES = 10

DELAY_BETWEEN_LISTINGS = (1.0, 2.5)
DELAY_BETWEEN_PAGES = (3.0, 6.0)
DELAY_BETWEEN_LOCALITIES = (8.0, 15.0)

COLUMNS = [
    "Locality", "City", "Project Name", "Price (INR)", "Area (SqFt)",
    "Price/SqFt", "BHK", "Bathrooms", "Property Type", "Furnishing",
    "Floor Number", "Total Floors", "Floor Info", "Construction Status",
    "Age of Property", "Source", "Scraped At",
]

# ──────────────────────────────────────────────
# All 126 localities
# ──────────────────────────────────────────────

LOCALITIES = [
    "Gachibowli", "Madhapur", "Kondapur", "Banjara Hills", "Jubilee Hills",
    "Hitech City", "Kukatpally", "Miyapur", "Manikonda", "Nallagandla",
    "Tellapur", "Narsingi", "Kokapet", "Financial District", "Nanakramguda",
    "Begumpet", "Ameerpet", "SR Nagar", "Balkampet", "Moosapet",
    "Bowenpally", "Secunderabad", "Tarnaka", "Malkajgiri", "Uppal",
    "Nagole", "LB Nagar", "Dilsukhnagar", "Vanasthalipuram", "Hayathnagar",
    "Sainikpuri", "Alwal", "Kompally", "Medchal", "Shamirpet",
    "Bachupally", "Nizampet", "Pragathi Nagar", "Chandanagar", "Mokila",
    "Shankarpally", "Rajendra Nagar", "Attapur", "Mehdipatnam", "Tolichowki",
    "Masab Tank", "Khairatabad", "Somajiguda", "Punjagutta", "Himayatnagar",
    "Shamshabad", "Adibatla", "Boduppal", "Ghatkesar", "Peerzadiguda",
    "Nacharam", "Habsiguda", "Moula Ali", "Charminar", "Falaknuma",
    "Yapral", "Bandlaguda", "Kothapet", "Suchitra", "ECIL",
    "Balanagar", "Suraram", "AS Rao Nagar", "Kapra", "Amberpet",
    "Nampally", "Abids", "Himayatsagar", "Patancheru", "Isnapur",
    "Toopran", "Sadashivpet", "Zaheerabad", "Tandur", "Vikarabad",
    "Chevella", "Ibrahimpatnam", "Nagaram", "Dammaiguda", "Dundigal",
    "Quthbullapur", "Jeedimetla", "Bahadurpura", "Santoshnagar", "Karmanghat",
    "Saroornagar", "Meerpet", "Badangpet", "Balapur", "Turkayamjal",
    "Musheerabad", "RTC X Roads", "Gandhi Nagar", "Koti", "Sultan Bazar",
    "King Koti", "Troop Bazar", "Chirag Ali Lane", "Narayanguda", "Vidyanagar",
    "Domalguda", "Goshamahal", "Barkatpura", "Greenlands", "Liberty",
    "Padmarao Nagar", "Marredpally", "West Marredpally", "Chilkalguda", "Trimulgherry",
    "Tilaknagar", "Karkhana", "SD Road", "Paradise", "Rasoolpura",
    "Bolarum", "Regimental Bazar", "Lalapet", "Ramanthapur", "Tukaram Gate",
    "Mallapur",
]

# ──────────────────────────────────────────────
# Locality name variants
# ──────────────────────────────────────────────

LOCALITY_VARIANTS: Dict[str, List[str]] = {
    "Hitech City":        ["Hitech City", "Hi-Tech City", "HITEC City", "Hitec City", "Hi Tech City"],
    "LB Nagar":           ["LB Nagar", "L.B. Nagar", "LBNagar", "L B Nagar", "Lb Nagar"],
    "AS Rao Nagar":       ["AS Rao Nagar", "A.S. Rao Nagar", "A S Rao Nagar", "ASRao Nagar"],
    "Financial District": ["Financial District", "Nanakramguda", "Financial Dist", "Fin District"],
    "RTC X Roads":        ["RTC X Roads", "RTC Crossroads", "RTC X Road", "RTC Cross Roads"],
    "SR Nagar":           ["SR Nagar", "S.R. Nagar", "S R Nagar", "Srinivasanagar"],
    "ECIL":               ["ECIL", "E.C.I.L", "ECIL Cross Roads", "ECIL Crossroads"],
    "SD Road":            ["SD Road", "S.D. Road", "Sardar Patel Road", "S D Road"],
    "Moula Ali":          ["Moula Ali", "Moulali", "Moula-Ali", "Mowla Ali"],
    "West Marredpally":   ["West Marredpally", "West Maredpally", "W Marredpally", "W. Marredpally"],
    "Pragathi Nagar":     ["Pragathi Nagar", "Pragati Nagar", "Pragathi Ngr", "Pragati Ngr"],
    "Marredpally":        ["Marredpally", "Maredpally", "Marred Pally"],
    "Chirag Ali Lane":    ["Chirag Ali Lane", "Chirag Ali", "Chiragali Lane"],
    "Regimental Bazar":   ["Regimental Bazar", "Regimental Bazaar"],
    "Tukaram Gate":       ["Tukaram Gate", "Tukaramgate", "Tukaram"],
    "King Koti":          ["King Koti", "Kingkoti", "King Kothi"],
    "Troop Bazar":        ["Troop Bazar", "Troop Bazaar", "Troopbazar"],
    "Sultan Bazar":       ["Sultan Bazar", "Sultan Bazaar", "Sultanbazar"],
    "Gandhi Nagar":       ["Gandhi Nagar", "Gandhingar", "Gandhi Ngr"],
    "Padmarao Nagar":     ["Padmarao Nagar", "Padmaraonagar", "Padma Rao Nagar"],
    "Quthbullapur":       ["Quthbullapur", "Qutbullapur", "Quthbulapur"],
    "Vanasthalipuram":    ["Vanasthalipuram", "Vanasthali Puram", "Vanastalipuram"],
    "Ibrahimpatnam":      ["Ibrahimpatnam", "Ibrahim Patnam", "Ibrahimpatna"],
    "Trimulgherry":       ["Trimulgherry", "Trimulgerry", "Trimulgheri"],
    "Peerzadiguda":       ["Peerzadiguda", "Peer Zadiguda", "Peerjadiguda"],
    "Himayatsagar":       ["Himayatsagar", "Himayat Sagar", "Himayat Nagar"],
}


def get_variants(locality: str) -> List[str]:
    if locality in LOCALITY_VARIANTS:
        return LOCALITY_VARIANTS[locality]
    return [
        locality,
        locality.replace(" ", ""),
        locality.title(),
        locality.lower(),
    ]


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def random_delay(low: float, high: float) -> None:
    time.sleep(random.uniform(low, high))


def get_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(options=options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    driver.implicitly_wait(10)
    return driver


# ──────────────────────────────────────────────
# Parsing helpers
# ──────────────────────────────────────────────

def parse_price_inr(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    text = text.strip().replace(",", "").replace("₹", "").strip()

    cr_match = re.search(r'([\d.]+)\s*(?:cr|crore)', text, re.IGNORECASE)
    if cr_match:
        return int(float(cr_match.group(1)) * 1_00_00_000)

    lac_match = re.search(r'([\d.]+)\s*(?:lac|lakh|l\b)', text, re.IGNORECASE)
    if lac_match:
        return int(float(lac_match.group(1)) * 1_00_000)

    k_match = re.search(r'([\d.]+)\s*(?:k|thousand)', text, re.IGNORECASE)
    if k_match:
        return int(float(k_match.group(1)) * 1_000)

    digits = re.sub(r'[^\d.]', '', text)
    if digits:
        try:
            return int(float(digits))
        except ValueError:
            pass
    return None


def parse_area_sqft(text: Optional[str]) -> Optional[float]:
    if not text:
        return None
    text = text.strip().replace(",", "")
    match = re.search(r'([\d.]+)\s*(?:sq\.?\s*ft|sqft|sft)', text, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    match = re.search(r'([\d.]+)', text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return None


def extract_bhk(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    match = re.search(r'(\d+)\s*(?:bhk|BHK|rk|RK)', text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def extract_bathrooms(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    match = re.search(r'(\d+)\s*(?:bath|bathroom|baths)', text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    try:
        return int(re.search(r'\d+', text).group())
    except Exception:
        return None


def extract_floor_info(text: Optional[str]) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    if not text or str(text).strip() in ('', 'nan', 'None'):
        return None, None, None

    raw = str(text).strip()
    text_lower = raw.lower()

    if 'ground' in text_lower or text_lower in ('g', 'gf'):
        return 0, None, raw
    if 'basement' in text_lower:
        return -1, None, raw

    match = re.search(r'(\d+)\s*(?:st|nd|rd|th)?\s*(?:out of|of|/|\\)\s*(\d+)', text_lower)
    if match:
        return int(match.group(1)), int(match.group(2)), raw

    match = re.search(r'^(\d+)', text_lower)
    if match:
        return int(match.group(1)), None, raw

    return None, None, raw


def classify_property_type(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    t = text.lower()
    if 'villa' in t:
        return 'Villa'
    if 'plot' in t or 'land' in t:
        return 'Plot'
    if 'independent' in t or 'house' in t or 'builder floor' in t:
        return 'Independent House'
    if 'apartment' in t or 'flat' in t:
        return 'Apartment'
    return text.strip()


def classify_furnishing(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    t = text.lower()
    if 'semi' in t:
        return 'Semi-Furnished'
    if 'unfurnished' in t or 'un-furnished' in t:
        return 'Unfurnished'
    if 'furnished' in t:
        return 'Furnished'
    return text.strip()


def classify_construction(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    t = text.lower()
    if 'ready' in t or 'move' in t:
        return 'Ready to Move'
    if 'under' in t or 'construction' in t or 'new launch' in t:
        return 'Under Construction'
    return text.strip()


# ──────────────────────────────────────────────
# CSV helpers
# ──────────────────────────────────────────────

def save_to_csv(rows: List[Dict], filepath: str) -> None:
    if not rows:
        return
    df = pd.DataFrame(rows, columns=COLUMNS)
    if os.path.exists(filepath):
        df.to_csv(filepath, mode='a', header=False, index=False)
    else:
        df.to_csv(filepath, mode='w', header=True, index=False)
    print(f"  Saved {len(rows)} rows to {filepath}")


def get_completed_localities(filepath: str) -> set:
    if not os.path.exists(filepath):
        return set()
    try:
        df = pd.read_csv(filepath)
        return set(df['Locality'].unique().tolist())
    except Exception:
        return set()


# ──────────────────────────────────────────────
# Housing.com-specific scraping
# ──────────────────────────────────────────────

def build_url(variant: str, page: int) -> str:
    """Build housing.com search URL for a locality in Hyderabad."""
    slug = variant.lower().replace(" ", "-").replace(".", "")
    if page == 1:
        return f"https://housing.com/in/buy/search?f=eyJiYXNlIjpbeyJ0eXBlIjoiTE9DQUxJVFkiLCJsYWJlbCI6IntzbHVnfSIsInZhbHVlIjoie3NsdWd9In1dfQ==&city=Hyderabad&q={variant}+Hyderabad"
    return f"https://housing.com/in/buy/search?f=eyJiYXNlIjpbeyJ0eXBlIjoiTE9DQUxJVFkiLCJsYWJlbCI6IntzbHVnfSIsInZhbHVlIjoie3NsdWd9In1dfQ==&city=Hyderabad&q={variant}+Hyderabad&page={page}"


def build_url_simple(variant: str, page: int) -> str:
    """Simpler housing.com URL using the buy path."""
    slug = variant.lower().replace(" ", "-").replace(".", "")
    if page == 1:
        return f"https://housing.com/in/buy/{slug}-hyderabad/residential-property"
    return f"https://housing.com/in/buy/{slug}-hyderabad/residential-property?page={page}"


def safe_text(element, selector: str, by=By.CSS_SELECTOR) -> Optional[str]:
    try:
        el = element.find_element(by, selector)
        txt = el.text.strip()
        return txt if txt else None
    except Exception:
        return None


def safe_attr(element, selector: str, attr: str, by=By.CSS_SELECTOR) -> Optional[str]:
    try:
        el = element.find_element(by, selector)
        val = el.get_attribute(attr)
        return val.strip() if val else None
    except Exception:
        return None


def scroll_to_load(driver: webdriver.Chrome, scrolls: int = 5) -> None:
    """Scroll down to trigger lazy loading of listing cards."""
    for _ in range(scrolls):
        driver.execute_script("window.scrollBy(0, 800);")
        time.sleep(0.8)


def extract_listing(card, standard_locality: str) -> Optional[Dict]:
    """Extract one listing row from a Housing.com property card."""
    try:
        # Project name
        project_name = (
            safe_text(card, "[class*='css-truncate']")
            or safe_text(card, "h2")
            or safe_text(card, "[data-test='project-name']")
            or safe_text(card, "[class*='listing-card-title']")
            or safe_text(card, "a[class*='body']")
        )

        # Price
        price_text = (
            safe_text(card, "[class*='price']")
            or safe_text(card, "[data-test='price']")
            or safe_text(card, "[class*='listing-card-price']")
        )
        price_inr = parse_price_inr(price_text)

        # Area
        area_text = (
            safe_text(card, "[class*='area']")
            or safe_text(card, "[data-test='super-area']")
            or safe_text(card, "[class*='carpet']")
        )
        area_sqft = parse_area_sqft(area_text)

        # Price per sqft
        ppsf_text = safe_text(card, "[class*='per-sqft']") or safe_text(card, "[class*='pricePerSqft']")
        price_per_sqft = None
        if ppsf_text:
            m = re.search(r'([\d,]+)', ppsf_text.replace(",", ""))
            if m:
                try:
                    price_per_sqft = float(m.group(1))
                except ValueError:
                    pass
        if price_per_sqft is None and price_inr and area_sqft and area_sqft > 0:
            price_per_sqft = round(price_inr / area_sqft, 2)

        # BHK
        bhk_text = (
            safe_text(card, "[class*='config']")
            or safe_text(card, "[data-test='bhk']")
            or (project_name or "")
        )
        bhk = extract_bhk(bhk_text)

        # Bathrooms
        bath_text = safe_text(card, "[class*='bath']")
        bathrooms = extract_bathrooms(bath_text)

        # Property type
        ptype_text = (
            safe_text(card, "[class*='property-type']")
            or safe_text(card, "[data-test='property-type']")
        )
        property_type = classify_property_type(ptype_text)

        # Furnishing
        furnishing_text = safe_text(card, "[class*='furnish']")
        furnishing = classify_furnishing(furnishing_text)

        # Floor info
        floor_text = safe_text(card, "[class*='floor']")
        floor_number, total_floors, floor_info = extract_floor_info(floor_text)

        # Construction status
        status_text = (
            safe_text(card, "[class*='possession']")
            or safe_text(card, "[class*='status']")
            or safe_text(card, "[data-test='possession']")
        )
        construction_status = classify_construction(status_text)

        # Age
        age_text = safe_text(card, "[class*='age']")
        age_of_property = age_text

        row = {
            'Locality':            standard_locality,
            'City':                'Hyderabad',
            'Project Name':        project_name,
            'Price (INR)':         price_inr,
            'Area (SqFt)':         area_sqft,
            'Price/SqFt':          price_per_sqft,
            'BHK':                 bhk,
            'Bathrooms':           bathrooms,
            'Property Type':       property_type,
            'Furnishing':          furnishing,
            'Floor Number':        floor_number,
            'Total Floors':        total_floors,
            'Floor Info':          floor_info,
            'Construction Status': construction_status,
            'Age of Property':     age_of_property,
            'Source':              SOURCE_NAME,
            'Scraped At':          datetime.now().isoformat(),
        }
        return row
    except Exception as e:
        print(f"    [ERROR] extract_listing: {e}")
        return None


def scrape_locality(driver: webdriver.Chrome, variant: str, standard_locality: str) -> List[Dict]:
    """Scrape all pages for a single locality variant on Housing.com."""
    rows: List[Dict] = []

    for page in range(1, MAX_PAGES + 1):
        url = build_url_simple(variant, page)
        print(f"    Page {page}: {url[:120]}...")

        try:
            driver.get(url)
            random_delay(2.0, 4.0)
        except Exception as e:
            print(f"    [ERROR] Loading page: {e}")
            break

        # Scroll down to load lazy content
        scroll_to_load(driver, scrolls=5)

        # Wait for listing cards
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    "[class*='listing-card'], [class*='css-'], [data-test='listing-card'], [class*='srpCard']"
                ))
            )
        except Exception:
            print(f"    Page {page}: no listings container — stopping pagination")
            break

        cards = driver.find_elements(By.CSS_SELECTOR, "[data-test='listing-card']")
        if not cards:
            cards = driver.find_elements(By.CSS_SELECTOR, "[class*='listing-card']")
        if not cards:
            cards = driver.find_elements(By.CSS_SELECTOR, "[class*='srpCard']")
        if not cards:
            # Housing.com often uses generic css class names
            cards = driver.find_elements(By.CSS_SELECTOR, "article, [role='article']")

        if not cards:
            print(f"    Page {page}: 0 cards — stopping")
            break

        print(f"    Page {page}: {len(cards)} cards found")

        for card in cards:
            row = extract_listing(card, standard_locality)
            if row:
                rows.append(row)
            random_delay(*DELAY_BETWEEN_LISTINGS)

        # Check for next page
        try:
            next_btn = driver.find_element(By.CSS_SELECTOR, "[class*='next'], [data-test='pagination-next']")
            if not next_btn.is_enabled():
                break
        except Exception:
            pass

        random_delay(*DELAY_BETWEEN_PAGES)

    return rows


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main() -> None:
    print(f"=== Housing.com Hyderabad Scraper ===")
    print(f"Output: {OUTPUT_FILE}")
    print(f"Localities: {len(LOCALITIES)}")

    completed = get_completed_localities(OUTPUT_FILE)
    remaining = [loc for loc in LOCALITIES if loc not in completed]
    print(f"Already done: {len(completed)} | Remaining: {len(remaining)}")

    if not remaining:
        print("All localities already scraped. Nothing to do.")
        return

    driver = get_driver()
    success_count = 0
    total_rows = 0
    failed_localities: List[str] = []

    try:
        for i, locality in enumerate(remaining, 1):
            print(f"\n[{i}/{len(remaining)}] {locality}")
            results_found = False
            variants = get_variants(locality)

            for variant in variants:
                print(f"  Trying variant: '{variant}'")
                rows = scrape_locality(driver, variant, locality)

                if rows:
                    save_to_csv(rows, OUTPUT_FILE)
                    print(f"  [OK] {locality} ('{variant}') — {len(rows)} rows")
                    total_rows += len(rows)
                    success_count += 1
                    results_found = True
                    break
                else:
                    print(f"  [MISS] variant '{variant}' — 0 results")

            if not results_found:
                print(f"  [WARN] {locality} — 0 results after {len(variants)} variants tried")
                failed_localities.append(locality)

            random_delay(*DELAY_BETWEEN_LOCALITIES)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Progress has been saved.")
    except Exception as e:
        print(f"\n\nFatal error: {e}. Progress has been saved.")
    finally:
        driver.quit()

    print("\n===== SCRAPE SUMMARY =====")
    print(f"Total localities attempted  : {len(remaining)}")
    print(f"Localities with data        : {success_count}")
    print(f"Localities with zero results: {len(failed_localities)}")
    if failed_localities:
        print(f"Failed: {failed_localities}")
    print(f"Total rows scraped          : {total_rows}")
    print(f"Output file                 : {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
