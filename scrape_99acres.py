"""
scrape_99acres.py  —  99acres Hyderabad scraper (undetected-chromedriver)
=========================================================================
Run:
    pip install undetected-chromedriver selenium pandas
    python scrape_99acres.py
"""

import os
import random
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd
import undetected_chromedriver as uc
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────

OUTPUT_FILE   = "99acres_hyderabad.csv"
SOURCE_NAME   = "99acres"
MAX_PAGES     = 10
RESTART_EVERY = 15

DELAY_LISTINGS   = (1.5, 3.0)
DELAY_PAGES      = (4.0, 7.0)
DELAY_LOCALITIES = (10.0, 18.0)
DELAY_ON_BLOCK   = (60.0, 120.0)

COLUMNS = [
    "Locality", "City", "Project Name", "Price (INR)", "Area (SqFt)",
    "Price/SqFt", "BHK", "Bathrooms", "Property Type", "Furnishing",
    "Floor Number", "Total Floors", "Floor Info", "Construction Status",
    "Age of Property", "Source", "Scraped At",
]

# ─────────────────────────────────────────────
# 126 Localities
# ─────────────────────────────────────────────

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

LOCALITY_VARIANTS: Dict[str, List[str]] = {
    "Hitech City":        ["Hitech City", "Hi-Tech City", "HITEC City", "Hitec City"],
    "LB Nagar":           ["LB Nagar", "L.B. Nagar", "LBNagar", "L B Nagar"],
    "AS Rao Nagar":       ["AS Rao Nagar", "A.S. Rao Nagar", "ASRao Nagar"],
    "Financial District": ["Financial District", "Nanakramguda", "Financial Dist"],
    "RTC X Roads":        ["RTC X Roads", "RTC Crossroads", "RTC X Road"],
    "SR Nagar":           ["SR Nagar", "S.R. Nagar", "Srinivasanagar"],
    "ECIL":               ["ECIL", "E.C.I.L", "ECIL Cross Roads"],
    "SD Road":            ["SD Road", "S.D. Road", "Sardar Patel Road"],
    "Moula Ali":          ["Moula Ali", "Moulali", "Moula-Ali"],
    "West Marredpally":   ["West Marredpally", "West Maredpally", "W Marredpally"],
    "Pragathi Nagar":     ["Pragathi Nagar", "Pragati Nagar"],
    "Marredpally":        ["Marredpally", "Maredpally"],
    "Chirag Ali Lane":    ["Chirag Ali Lane", "Chirag Ali"],
    "Regimental Bazar":   ["Regimental Bazar", "Regimental Bazaar"],
    "Tukaram Gate":       ["Tukaram Gate", "Tukaramgate"],
    "King Koti":          ["King Koti", "King Kothi"],
    "Troop Bazar":        ["Troop Bazar", "Troop Bazaar"],
    "Sultan Bazar":       ["Sultan Bazar", "Sultan Bazaar"],
    "Gandhi Nagar":       ["Gandhi Nagar", "Gandhingar"],
    "Padmarao Nagar":     ["Padmarao Nagar", "Padma Rao Nagar"],
    "Quthbullapur":       ["Quthbullapur", "Qutbullapur"],
    "Vanasthalipuram":    ["Vanasthalipuram", "Vanasthali Puram"],
    "Ibrahimpatnam":      ["Ibrahimpatnam", "Ibrahim Patnam"],
    "Trimulgherry":       ["Trimulgherry", "Trimulgerry"],
    "Peerzadiguda":       ["Peerzadiguda", "Peer Zadiguda"],
    "Himayatsagar":       ["Himayatsagar", "Himayat Sagar"],
    "Narayanguda":        ["Narayanguda", "Narayan Guda"],
    "Dilsukhnagar":       ["Dilsukhnagar", "Dilsuk Nagar"],
    "Hayathnagar":        ["Hayathnagar", "Hayath Nagar"],
}


def get_variants(locality: str) -> List[str]:
    return LOCALITY_VARIANTS.get(locality, [
        locality,
        locality.replace(" ", "-"),
        locality.title(),
        locality.lower(),
    ])


# ─────────────────────────────────────────────
# Driver
# ─────────────────────────────────────────────

def get_driver() -> uc.Chrome:
    options = uc.ChromeOptions()
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--lang=en-US")
    driver = uc.Chrome(options=options, use_subprocess=True)
    driver.set_page_load_timeout(40)
    driver.set_script_timeout(30)
    return driver


def random_delay(low: float, high: float) -> None:
    time.sleep(random.uniform(low, high))


# ─────────────────────────────────────────────
# Parsers
# ─────────────────────────────────────────────

def parse_price_inr(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    text = str(text).strip().replace(",", "").replace("₹", "").replace("\u20b9", "")
    m = re.search(r'([\d.]+)\s*(?:cr|crore)', text, re.IGNORECASE)
    if m:
        return int(float(m.group(1)) * 1_00_00_000)
    m = re.search(r'([\d.]+)\s*(?:lac|lakh|l\b)', text, re.IGNORECASE)
    if m:
        return int(float(m.group(1)) * 1_00_000)
    m = re.search(r'([\d.]+)\s*(?:k\b|thousand)', text, re.IGNORECASE)
    if m:
        return int(float(m.group(1)) * 1_000)
    digits = re.sub(r'[^\d.]', '', text)
    try:
        return int(float(digits)) if digits else None
    except ValueError:
        return None


def parse_area_sqft(text: Optional[str]) -> Optional[float]:
    if not text:
        return None
    text = str(text).replace(",", "")
    m = re.search(r'([\d.]+)\s*(?:sq\.?\s*ft|sqft|sft)', text, re.IGNORECASE)
    if m:
        return float(m.group(1))
    m = re.search(r'([\d.]+)', text)
    return float(m.group(1)) if m else None


def extract_bhk(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    m = re.search(r'(\d+)\s*(?:bhk|rk)', str(text), re.IGNORECASE)
    return int(m.group(1)) if m else None


def extract_bathrooms(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    m = re.search(r'(\d+)\s*(?:bath|bathroom)', str(text), re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r'\d+', str(text))
    return int(m.group()) if m else None


def extract_floor_info(text: Optional[str]) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    if not text or str(text).strip().lower() in ('', 'nan', 'none', '-'):
        return None, None, None
    raw = str(text).strip()
    tl  = raw.lower()
    if any(w in tl for w in ('ground', 'g floor', 'gf')):
        return 0, None, raw
    if 'basement' in tl:
        return -1, None, raw
    m = re.search(r'(\d+)\s*(?:st|nd|rd|th)?\s*(?:out of|of|/|\\)\s*(\d+)', tl)
    if m:
        return int(m.group(1)), int(m.group(2)), raw
    m = re.search(r'(\d+)', tl)
    return (int(m.group(1)), None, raw) if m else (None, None, raw)


def classify_property_type(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    t = str(text).lower()
    if 'villa' in t:                          return 'Villa'
    if 'plot' in t or 'land' in t:           return 'Plot'
    if 'independent' in t or 'builder' in t: return 'Independent House'
    if 'apartment' in t or 'flat' in t:      return 'Apartment'
    return text.strip()


def classify_furnishing(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    t = str(text).lower()
    if 'semi' in t:      return 'Semi-Furnished'
    if 'unfurnish' in t: return 'Unfurnished'
    if 'furnish' in t:   return 'Furnished'
    return None


def classify_construction(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    t = str(text).lower()
    if 'ready' in t or 'move' in t:      return 'Ready to Move'
    if 'under' in t or 'construct' in t: return 'Under Construction'
    return text.strip()


# ─────────────────────────────────────────────
# CSV helpers
# ─────────────────────────────────────────────

def save_to_csv(rows: List[Dict], filepath: str) -> None:
    if not rows:
        return
    df = pd.DataFrame(rows, columns=COLUMNS)
    write_header = not os.path.exists(filepath)
    df.to_csv(filepath, mode='a', header=write_header, index=False)
    print(f"  Saved {len(rows)} rows -> {filepath}")


def get_completed_localities(filepath: str) -> set:
    if not os.path.exists(filepath):
        return set()
    try:
        return set(pd.read_csv(filepath, usecols=["Locality"])["Locality"].dropna().unique())
    except Exception:
        return set()


# ─────────────────────────────────────────────
# DOM helpers & selectors
# ─────────────────────────────────────────────

def safe_text(el, css: str) -> Optional[str]:
    try:
        t = el.find_element(By.CSS_SELECTOR, css).text.strip()
        return t or None
    except Exception:
        return None


def first_match(el, selectors: List[str]) -> Optional[str]:
    for s in selectors:
        v = safe_text(el, s)
        if v:
            return v
    return None


CARD_SELECTORS = [
    "[id^='srp_tuple_']",
    "[class*='srpTuple__tupleTable']",
    "[class*='tupleNew__tupleTable']",
    "[class*='projectTuple__details']",
    "article[class*='listing']",
    "li[class*='tuple']",
]

PRICE_SELECTORS  = ["[class*='list_header_semiBold']", "[class*='srpTuple__price']", "[class*='price__amount']", "[class*='price']"]
AREA_SELECTORS   = ["[class*='carpetArea']", "[class*='builtup']", "[class*='area']", "[class*='size']"]
FLOOR_SELECTORS  = ["[class*='floor']", "[class*='Floor']", "li[class*='floorDetails']"]
STATUS_SELECTORS = ["[class*='srpTuple__status']", "[class*='possession']", "[class*='status']"]


def is_blocked(driver: uc.Chrome) -> bool:
    signals = ['captcha', 'robot', 'access denied', 'blocked', 'verify you are human']
    try:
        src = driver.page_source.lower()
        return any(s in src for s in signals)
    except Exception:
        return False


def build_url(variant: str, page: int) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', variant.lower()).strip('-')
    base = f"https://www.99acres.com/search/property/buy/{slug}-hyderabad?city=37&preference=S&area_unit=1&res_com=R"
    return base if page == 1 else f"{base}&page={page}"


# ─────────────────────────────────────────────
# Listing extractor
# ─────────────────────────────────────────────

def extract_listing(card, locality: str) -> Optional[Dict]:
    try:
        full_text = ""
        try:
            full_text = card.text or ""
        except Exception:
            pass

        project_name = safe_text(card, "[class*='projectName']") or safe_text(card, "h2") or safe_text(card, "[class*='title']")

        price_text = first_match(card, PRICE_SELECTORS)
        if not price_text:
            m = re.search(r'[\u20b9]?\s*[\d,.]+\s*(?:cr|crore|lac|lakh|l\b)', full_text, re.IGNORECASE)
            price_text = m.group(0) if m else None
        price_inr = parse_price_inr(price_text)

        area_text = first_match(card, AREA_SELECTORS)
        area_sqft = parse_area_sqft(area_text)

        ppsf_text = safe_text(card, "[class*='perSqFt']") or safe_text(card, "[class*='pricePerSqft']")
        price_per_sqft: Optional[float] = None
        if ppsf_text:
            m = re.search(r'([\d,]+)', ppsf_text.replace(",", ""))
            if m:
                try:
                    price_per_sqft = float(m.group(1))
                except ValueError:
                    pass
        if not price_per_sqft and price_inr and area_sqft and area_sqft > 0:
            price_per_sqft = round(price_inr / area_sqft, 2)

        bhk = extract_bhk(safe_text(card, "[class*='bhk']") or safe_text(card, "[class*='config']") or project_name or full_text)
        bathrooms = extract_bathrooms(safe_text(card, "[class*='bath']") or full_text)
        property_type = classify_property_type(safe_text(card, "[class*='propertyType']") or project_name or full_text)
        furnishing = classify_furnishing(safe_text(card, "[class*='furnish']") or full_text)

        floor_text = first_match(card, FLOOR_SELECTORS)
        if not floor_text:
            m = re.search(r'(\d+\s*(?:st|nd|rd|th)?\s*(?:out of|/)\s*\d+|ground floor|basement)', full_text, re.IGNORECASE)
            floor_text = m.group(0) if m else None
        floor_number, total_floors, floor_info = extract_floor_info(floor_text)

        construction_status = classify_construction(first_match(card, STATUS_SELECTORS) or full_text)
        age_text = safe_text(card, "[class*='ageOf']") or safe_text(card, "[class*='age']")

        return {
            'Locality':            locality,
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
            'Age of Property':     age_text,
            'Source':              SOURCE_NAME,
            'Scraped At':          datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"    [ERROR] extract_listing: {e}")
        return None


# ─────────────────────────────────────────────
# Per-locality scraper
# ─────────────────────────────────────────────

def scrape_locality(driver: uc.Chrome, variant: str, locality: str) -> List[Dict]:
    rows: List[Dict] = []

    for page in range(1, MAX_PAGES + 1):
        url = build_url(variant, page)
        print(f"    Page {page}: {url[:100]}...")

        try:
            driver.get(url)
            random_delay(3.0, 6.0)
        except WebDriverException as e:
            print(f"    [ERROR] Page load: {e}")
            break

        if is_blocked(driver):
            print(f"    [BLOCK] Waiting {int(DELAY_ON_BLOCK[0])}s...")
            random_delay(*DELAY_ON_BLOCK)
            try:
                driver.get(url)
                random_delay(4.0, 8.0)
            except Exception:
                break
            if is_blocked(driver):
                print(f"    [BLOCK] Still blocked — skipping")
                break

        try:
            WebDriverWait(driver, 20).until(
                lambda d: (
                    any(d.find_elements(By.CSS_SELECTOR, s) for s in CARD_SELECTORS)
                    or d.find_elements(By.CSS_SELECTOR, "[class*='noResult'],[class*='no-result'],[class*='zeroResult']")
                )
            )
        except TimeoutException:
            print(f"    Timeout page {page} — stopping")
            break

        if driver.find_elements(By.CSS_SELECTOR, "[class*='noResult'],[class*='no-result'],[class*='zeroResult']"):
            print(f"    No results — stopping")
            break

        cards = []
        for sel in CARD_SELECTORS:
            cards = driver.find_elements(By.CSS_SELECTOR, sel)
            if cards:
                break

        if not cards:
            print(f"    0 cards — stopping")
            break

        print(f"    {len(cards)} cards")
        for card in cards:
            row = extract_listing(card, locality)
            if row:
                rows.append(row)
            random_delay(*DELAY_LISTINGS)

        try:
            nxt = driver.find_elements(By.CSS_SELECTOR, "a[class*='pageNext'],a[aria-label='Next'],li.next > a")
            if not nxt or not nxt[0].is_enabled():
                break
        except Exception:
            pass

        random_delay(*DELAY_PAGES)

    return rows


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main() -> None:
    print("=== 99acres Hyderabad Scraper (undetected-chromedriver) ===")
    print(f"Output: {OUTPUT_FILE} | Localities: {len(LOCALITIES)}")

    completed = get_completed_localities(OUTPUT_FILE)
    remaining = [l for l in LOCALITIES if l not in completed]
    print(f"Done: {len(completed)} | Remaining: {len(remaining)}")

    if not remaining:
        print("All done!")
        return

    driver        = get_driver()
    success_count = 0
    total_rows    = 0
    failed: List[str] = []

    try:
        for i, locality in enumerate(remaining, 1):

            if i > 1 and (i - 1) % RESTART_EVERY == 0:
                print(f"\n[DRIVER] Restarting Chrome...")
                try:
                    driver.quit()
                except Exception:
                    pass
                random_delay(8.0, 15.0)
                driver = get_driver()

            print(f"\n[{i}/{len(remaining)}] {locality}")
            found = False

            for variant in get_variants(locality):
                print(f"  Trying: '{variant}'")
                rows = scrape_locality(driver, variant, locality)
                if rows:
                    save_to_csv(rows, OUTPUT_FILE)
                    print(f"  [OK] {locality} via '{variant}' — {len(rows)} rows")
                    total_rows    += len(rows)
                    success_count += 1
                    found = True
                    break
                print(f"  [MISS] '{variant}' — 0 rows")

            if not found:
                print(f"  [WARN] {locality} — no data after all variants")
                failed.append(locality)

            random_delay(*DELAY_LOCALITIES)

    except KeyboardInterrupt:
        print("\nStopped by user. Progress saved.")
    except Exception as e:
        print(f"\nFatal: {e}. Progress saved.")
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    print("\n" + "=" * 45)
    print("SCRAPE SUMMARY")
    print("=" * 45)
    print(f"Attempted  : {len(remaining)}")
    print(f"With data  : {success_count}")
    print(f"No results : {len(failed)}")
    if failed:
        print(f"Failed     : {failed}")
    print(f"Total rows : {total_rows}")
    print(f"Saved to   : {OUTPUT_FILE}")


if __name__ == "__main__":
    main()