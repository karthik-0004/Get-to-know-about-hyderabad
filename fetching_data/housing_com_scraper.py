# housing_com_scraper.py

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import json
import re
from datetime import datetime
import os

# ─────────────────────────────────────────────
# MAIN FOLDER ON DESKTOP
# ─────────────────────────────────────────────
DESKTOP_PATH = os.path.join(os.path.expanduser("~"), "Desktop")
MAIN_FOLDER  = os.path.join(DESKTOP_PATH, "HousingCom_Housing_Data")
os.makedirs(MAIN_FOLDER, exist_ok=True)

# ─────────────────────────────────────────────
# ALL HYDERABAD LOCALITIES
# ─────────────────────────────────────────────
LOCALITIES = [
    # Central Hyderabad
    # "Abids", 
    # "Basheerbagh", "Lakdikapul", "Khairatabad",
    # "Himayatnagar", "Narayanaguda", "Chikkadpally", "RTC X Roads",
    # "Musheerabad", "Koti", "Chaderghat", "Malakpet", "Amberpet",
    # "Bagh Amberpet", "Vidyanagar", "Ram Nagar", "Sultan Bazar",
    # "Masab Tank",

    # # Secunderabad & North
    "Secunderabad",
    # 
    #  "Begumpet", "Trimulgherry", "Alwal",
    # "Bowenpally", "Old Bowenpally", "Tarnaka", "Malkajgiri",
    # "Sainikpuri", "ECIL", "Kapra", "Dammaiguda", "Kompally",
    # "Medchal", "Shamirpet", "Jeedimetla", "Suchitra", "Quthbullapur",

    # # West Hyderabad
    "Kukatpally", 
    # "KPHB Colony", "Miyapur", "Bachupally",
    # "Nizampet", "Pragathi Nagar", "Hydernagar", "Moosapet",
    # "Erragadda", "Sanath Nagar", "Balanagar", "Chintal",
    # "Gajularamaram", "Suraram", "Patancheru", "Beeramguda", "Ameenpur",

    # # IT & Financial Corridor
    # "Madhapur", "Hitech City", "Gachibowli", "Kondapur",
    # "Manikonda", "Puppalguda", "Nallagandla", "Tellapur",
    # "Narsingi", "Kokapet", "Financial District", "Nanakramguda",
    # "Raidurg", "Khanamet", "Gowlidoddy", "Gopanpally",
    # "Serilingampally", "Hafeezpet", "Madinaguda", "Lingampally",

    # # Premium Areas
    # "Banjara Hills", "Jubilee Hills", "Film Nagar",
    # "Shaikpet", "Tolichowki", "Srinagar Colony", "Yousufguda",

    # # South Hyderabad
    # "Mehdipatnam", "Attapur", "Rajendranagar", "Bandlaguda Jagir",
    # "Upparpally", "Kismatpur", "Gudimalkapur", "Asif Nagar", "Red Hills",

    # # East Hyderabad
    # "LB Nagar", "Dilsukhnagar", "Nagole", "Uppal", "Habsiguda",
    # "Nacharam", "Moula Ali", "Boduppal", "Peerzadiguda",
    # "Medipally", "Pocharam", "Ghatkesar", "Hayathnagar",
    # "Vanastalipuram", "Champapet", "Saroornagar", "Karmanghat",
    # "Badangpet", "Meerpet",

    # # Old City
    # "Charminar", "Falaknuma", "Bahadurpura", "Yakutpura",
    # "Chandrayangutta", "Santoshnagar", "Dabeerpura", "Katedan",

    # # Airport & Outskirts
    # "Shamshabad", "Adibatla", "Maheshwaram", "Kandukur",
    # "Ibrahimpatnam", "Balapur", "Shadnagar", "Turkapally", "Bibinagar",
]


# ─────────────────────────────────────────────
# REGEX PARSERS
# ─────────────────────────────────────────────
def parse_bhk(text):
    if not text or text == "N/A":
        return "N/A"
    match = re.search(r'(\d+)\s*(BHK|RK|Bedroom|bedroom)', text, re.IGNORECASE)
    if match:
        return f"{match.group(1)} BHK"
    return "N/A"


def parse_area(text):
    if not text or text == "N/A":
        return "N/A"
    match = re.search(
        r'([\d,]+\.?\d*)\s*(sq\.?ft|sqft|Sq\.?Ft|SqFt)',
        text, re.IGNORECASE
    )
    if match:
        return match.group(1).replace(",", "") + " sqft"
    return "N/A"


def parse_price(text):
    if not text or text == "N/A":
        return "N/A"
    match = re.search(r'₹\s*([\d,.]+)\s*(Cr|Lac|L|K)?', text, re.IGNORECASE)
    if match:
        return f"₹{match.group(1)} {match.group(2) or ''}".strip()
    return "N/A"


def parse_price_per_sqft(text):
    if not text or text == "N/A":
        return "N/A"
    match = re.search(r'₹\s*([\d,]+)\s*/\s*sq', text, re.IGNORECASE)
    if match:
        return f"₹{match.group(1)}/sqft"
    return "N/A"


def parse_property_type(text):
    if not text or text == "N/A":
        return "N/A"
    types = [
        "Penthouse", "Builder Floor", "Independent House",
        "Farm House", "Row House", "Studio Apartment",
        "Apartment", "Flat", "Villa", "Plot", "Land",
        "Office Space", "Shop"
    ]
    for t in types:
        if t.lower() in text.lower():
            return t
    return "N/A"


def parse_furnishing(text):
    if not text or text == "N/A":
        return "N/A"
    if re.search(r'semi.?furnished', text, re.IGNORECASE):
        return "Semi-Furnished"
    if re.search(r'unfurnished|un.furnished', text, re.IGNORECASE):
        return "Unfurnished"
    if re.search(r'\bfurnished\b', text, re.IGNORECASE):
        return "Furnished"
    return "N/A"


def parse_floor(text):
    if not text or text == "N/A":
        return "N/A"
    match = re.search(r'(\d+)\s*(st|nd|rd|th)?\s*[Ff]loor', text)
    if match:
        return match.group(1)
    return "N/A"


def parse_total_floors(text):
    if not text or text == "N/A":
        return "N/A"
    match = re.search(r'out\s+of\s+(\d+)', text, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r'(\d+)\s*[Ff]loors?\s*[Tt]otal', text)
    if match:
        return match.group(1)
    return "N/A"


def parse_bathrooms(text):
    if not text or text == "N/A":
        return "N/A"
    match = re.search(r'(\d+)\s*(Bath|Bathroom|bath|bathroom)', text)
    if match:
        return match.group(1)
    return "N/A"


def parse_posted_by(text):
    if not text or text == "N/A":
        return "N/A"
    roles = ["Owner", "Builder", "Agent", "Dealer", "Broker", "Developer"]
    for r in roles:
        if r.lower() in text.lower():
            return r
    return "N/A"


def parse_posted_on(text):
    if not text or text == "N/A":
        return "N/A"
    match = re.search(
        r'(\d+\s*(day|week|month|hour|min|mo|yr|year)s?\s*ago)',
        text, re.IGNORECASE
    )
    if match:
        return match.group(1)
    return "N/A"


def parse_locality(text, fallback):
    if not text or text == "N/A":
        return fallback
    text = re.sub(r',?\s*Hyderabad.*$', '', text, flags=re.IGNORECASE).strip()
    return text if text else fallback


# ─────────────────────────────────────────────
# DRIVER SETUP
# ─────────────────────────────────────────────
def create_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-extensions")
    options.add_argument("--log-level=3")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
    options.add_experimental_option(
        "excludeSwitches", ["enable-automation", "enable-logging"]
    )
    options.add_experimental_option("useAutomationExtension", False)
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


# ─────────────────────────────────────────────
# EXTRACT LISTINGS
# ─────────────────────────────────────────────
def extract_listings(soup, locality):
    properties = []

    def txt(el):
        return " ".join(el.get_text(strip=True).split()) if el else "N/A"

    # ── Method 1: __NEXT_DATA__ JSON deep search ──
    script_tag = soup.find("script", {"id": "__NEXT_DATA__"})
    if script_tag:
        try:
            data = json.loads(script_tag.string)

            def deep_find(obj, depth=0):
                if depth > 10:
                    return []
                if isinstance(obj, list) and len(obj) > 0:
                    first = obj[0]
                    if isinstance(first, dict):
                        keys = set(str(k).lower() for k in first.keys())
                        if keys & {
                            "price", "area", "bedroom_count",
                            "locality_name", "listing_type",
                            "carpet_area", "display_price"
                        }:
                            return obj
                if isinstance(obj, dict):
                    for v in obj.values():
                        result = deep_find(v, depth + 1)
                        if result:
                            return result
                if isinstance(obj, list):
                    for item in obj:
                        result = deep_find(item, depth + 1)
                        if result:
                            return result
                return []

            listings = deep_find(data)
            for item in listings:
                raw_text  = " ".join(str(v) for v in item.values())

                price     = str(item.get("display_price",       item.get("price",           "N/A")))
                psqft     = str(item.get("price_per_unit_area", item.get("price_per_sqft",  "N/A")))
                area      = str(item.get("carpet_area",         item.get("area",            "N/A")))
                bhk       = str(item.get("bedroom_count",       item.get("bhk",             "N/A")))
                bath      = str(item.get("bathroom_count",      item.get("bathrooms",       "N/A")))
                ptype     = str(item.get("property_type",       item.get("listing_type",    "N/A")))
                furnish   = str(item.get("furnishing_type",     item.get("furnishing",      "N/A")))
                floor     = str(item.get("floor_number",        item.get("floor",           "N/A")))
                tot_floor = str(item.get("total_floors",        item.get("totalFloors",     "N/A")))
                posted_by = str(item.get("posted_by",           item.get("owner_type",      "N/A")))
                posted_on = str(item.get("posted_at",           item.get("listed_date",     "N/A")))
                loc       = str(item.get("locality_name",       item.get("locality",        locality)))
                proj_name = str(item.get("society_name",        item.get("project_name",    item.get("name", "N/A"))))

                # Regex fallbacks
                if price     in ("N/A", "None", ""): price     = parse_price(raw_text)
                if psqft     in ("N/A", "None", ""): psqft     = parse_price_per_sqft(raw_text)
                if area      in ("N/A", "None", ""): area      = parse_area(raw_text)
                if bhk       in ("N/A", "None", ""): bhk       = parse_bhk(raw_text)
                if bath      in ("N/A", "None", ""): bath      = parse_bathrooms(raw_text)
                if ptype     in ("N/A", "None", ""): ptype     = parse_property_type(raw_text)
                if furnish   in ("N/A", "None", ""): furnish   = parse_furnishing(raw_text)
                if floor     in ("N/A", "None", ""): floor     = parse_floor(raw_text)
                if tot_floor in ("N/A", "None", ""): tot_floor = parse_total_floors(raw_text)
                if posted_by in ("N/A", "None", ""): posted_by = parse_posted_by(raw_text)
                if posted_on in ("N/A", "None", ""): posted_on = parse_posted_on(raw_text)

                # BHK from project name if still missing
                if bhk in ("N/A", "None", ""):
                    bhk = parse_bhk(proj_name)

                # Convert BHK number to string like "3 BHK"
                if bhk not in ("N/A", "None", "") and str(bhk).isdigit():
                    bhk = f"{bhk} BHK"

                properties.append({
                    "Locality":      parse_locality(loc, locality),
                    "City":          "Hyderabad",
                    "Project Name":  proj_name,
                    "Price (INR)":   price,
                    "Price/SqFt":    psqft,
                    "Area (SqFt)":   area,
                    "BHK":           bhk,
                    "Bathrooms":     bath,
                    "Property Type": ptype,
                    "Furnishing":    furnish,
                    "Floor":         floor,
                    "Total Floors":  tot_floor,
                    "Listed By":     posted_by,
                    "Posted On":     posted_on,
                    "Source":        "housing.com",
                    "Scraped At":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })

            if properties:
                return properties

        except Exception:
            pass

    # ── Method 2: HTML card fallback with smart parsing ──
    cards = soup.select(
        "div[data-testid='srp-listing-card'], "
        "div.css-1n0bzds, "
        "li.propertyCard, "
        "div[class*='listing-card'], "
        "div[class*='property-card'], "
        "div[class*='srpCard'], "
        "div[class*='card__container']"
    )

    for card in cards:
        full_text  = card.get_text(separator=" ", strip=True)

        title_el   = card.select_one(
            "[data-testid='listing-title'], "
            "[class*='title'], h2, h3"
        )
        loc_el     = card.select_one(
            "[data-testid='listing-locality'], "
            "[class*='locality'], [class*='location'], "
            "[class*='address']"
        )
        price_el   = card.select_one(
            "[data-testid='listing-price'], "
            "[class*='price']"
        )
        area_el    = (
            card.select_one("[data-testid='listing-area']")
            or card.select_one("[class*='area']")
            or card.select_one("span:-soup-contains('sq.ft')")
            or card.select_one("span:-soup-contains('Sq.Ft')")
            or card.select_one("li:-soup-contains('Sq.Ft')")
        )
        bhk_el     = (
            card.select_one("[data-testid='listing-bhk']")
            or card.select_one("[class*='bhk']")
            or card.select_one("[class*='bedroom']")
            or card.select_one("span:-soup-contains('BHK')")
            or card.select_one("li:-soup-contains('BHK')")
        )
        bath_el    = (
            card.select_one("[class*='bath']")
            or card.select_one("span:-soup-contains('Bath')")
            or card.select_one("li:-soup-contains('Bath')")
        )
        ptype_el   = (
            card.select_one("[class*='property-type']")
            or card.select_one("[class*='prop-type']")
            or card.select_one("span:-soup-contains('Apartment')")
            or card.select_one("span:-soup-contains('Villa')")
            or card.select_one("span:-soup-contains('Flat')")
            or card.select_one("span:-soup-contains('Plot')")
            or card.select_one("li:-soup-contains('Apartment')")
        )
        psqft_el   = (
            card.select_one("[class*='per-sqft']")
            or card.select_one("[class*='price-sqft']")
            or card.select_one("span:-soup-contains('/ sq.ft')")
            or card.select_one("span:-soup-contains('/sqft')")
        )
        floor_el   = (
            card.select_one("[class*='floor']")
            or card.select_one("span:-soup-contains('Floor')")
            or card.select_one("li:-soup-contains('Floor')")
        )
        furnish_el = (
            card.select_one("[class*='furnish']")
            or card.select_one("span:-soup-contains('Furnished')")
            or card.select_one("span:-soup-contains('Unfurnished')")
        )
        listed_el  = (
            card.select_one("[class*='owner']")
            or card.select_one("[class*='posted-by']")
            or card.select_one("[class*='agent']")
            or card.select_one("span:-soup-contains('Owner')")
            or card.select_one("span:-soup-contains('Builder')")
            or card.select_one("span:-soup-contains('Agent')")
        )
        posted_el  = (
            card.select_one("[class*='posted']")
            or card.select_one("[class*='time']")
            or card.select_one("span:-soup-contains('ago')")
        )

        # Extract — CSS selector first, regex fallback on full card text
        price     = txt(price_el);    price     = parse_price(full_text)          if price    == "N/A" else price
        area      = txt(area_el);     area      = parse_area(full_text)           if area     == "N/A" else area
        bhk       = txt(bhk_el);      bhk       = parse_bhk(full_text)            if bhk      == "N/A" else bhk
        bath      = txt(bath_el);     bath      = parse_bathrooms(full_text)      if bath     == "N/A" else bath
        ptype     = txt(ptype_el);    ptype     = parse_property_type(full_text)  if ptype    == "N/A" else ptype
        psqft     = txt(psqft_el);    psqft     = parse_price_per_sqft(full_text) if psqft    == "N/A" else psqft
        floor     = txt(floor_el);    floor     = parse_floor(full_text)          if floor    == "N/A" else floor
        furnish   = txt(furnish_el);  furnish   = parse_furnishing(full_text)     if furnish  == "N/A" else furnish
        posted_by = txt(listed_el);   posted_by = parse_posted_by(full_text)      if posted_by== "N/A" else posted_by
        posted_on = txt(posted_el);   posted_on = parse_posted_on(full_text)      if posted_on== "N/A" else posted_on
        tot_floor = parse_total_floors(full_text)
        loc       = parse_locality(txt(loc_el), locality)

        # BHK from title if still missing
        if bhk == "N/A":
            bhk = parse_bhk(txt(title_el))

        # Convert numeric BHK to readable format
        if bhk not in ("N/A", "None", "") and str(bhk).isdigit():
            bhk = f"{bhk} BHK"

        if not any([txt(title_el), price, area, bhk]):
            continue

        properties.append({
            "Locality":      loc,
            "City":          "Hyderabad",
            "Project Name":  txt(title_el),
            "Price (INR)":   price,
            "Price/SqFt":    psqft,
            "Area (SqFt)":   area,
            "BHK":           bhk,
            "Bathrooms":     bath,
            "Property Type": ptype,
            "Furnishing":    furnish,
            "Floor":         floor,
            "Total Floors":  tot_floor,
            "Listed By":     posted_by,
            "Posted On":     posted_on,
            "Source":        "housing.com",
            "Scraped At":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

    return properties


# ─────────────────────────────────────────────
# SCRAPE ONE LOCALITY
# ─────────────────────────────────────────────
def scrape_locality(driver, locality):
    slug = locality.lower().replace(" ", "-")
    url  = f"https://housing.com/in/buy/{slug}-hyderabad/real-estate-{slug}-hyderabad"

    try:
        driver.get(url)
        time.sleep(random.uniform(4, 6))

        page_text = driver.page_source.lower()
        no_result_phrases = [
            "no properties found", "no results found",
            "0 properties", "couldn't find", "no listing",
            "no property found", "currently no properties",
            "we couldn't find", "no properties available",
        ]
        if any(phrase in page_text for phrase in no_result_phrases):
            return []

        for _ in range(5):
            driver.execute_script("window.scrollBy(0, window.innerHeight);")
            time.sleep(random.uniform(0.8, 1.2))
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        return extract_listings(soup, locality)

    except Exception as e:
        print(f"    [ERROR] {locality}: {e}")
        return []


# ─────────────────────────────────────────────
# SAVE ONE LOCALITY CSV
# ─────────────────────────────────────────────
def save_locality_csv(df, locality):
    safe_name = locality.replace(" ", "_").replace("/", "_")
    filepath  = os.path.join(MAIN_FOLDER, f"{safe_name}.csv")
    df.to_csv(filepath, index=False, encoding="utf-8-sig")
    return filepath


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  housing.com Hyderabad Housing Scraper")
    print("=" * 60)
    print(f"  Started At      : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Total Localities: {len(LOCALITIES)}")
    print(f"  Saving To       : {MAIN_FOLDER}")
    print("=" * 60)

    driver        = create_driver()
    saved_files   = []
    skipped       = []
    total_records = 0

    print("\n  [OK] Browser launched.\n")

    try:
        for idx, locality in enumerate(LOCALITIES, 1):
            print(f"  [{idx:>3}/{len(LOCALITIES)}] {locality}")
            listings = scrape_locality(driver, locality)

            if not listings:
                skipped.append(locality)
                print(f"           → Skipped (no data)")
                time.sleep(random.uniform(1, 2))
                continue

            df = pd.DataFrame(listings)

            # Drop rows where all key fields are N/A
            df = df[~(
                (df["Price (INR)"] == "N/A") &
                (df["Area (SqFt)"] == "N/A") &
                (df["BHK"]         == "N/A")
            )]

            # Remove duplicates
            df.drop_duplicates(
                subset=["Price (INR)", "Area (SqFt)", "BHK", "Project Name"],
                inplace=True
            )
            df.reset_index(drop=True, inplace=True)

            if df.empty:
                skipped.append(locality)
                print(f"           → Skipped (empty after cleaning)")
                continue

            filepath = save_locality_csv(df, locality)
            saved_files.append(filepath)
            total_records += len(df)
            print(f"           → Saved {len(df):>3} listings → {os.path.basename(filepath)}")
            time.sleep(random.uniform(2, 4))

    finally:
        driver.quit()
        print("\n  Browser closed.")

    # ── Final Summary ──
    print("\n" + "=" * 60)
    print("  SCRAPING COMPLETE!")
    print("=" * 60)
    print(f"  Folder         : {MAIN_FOLDER}")
    print(f"  CSV Files Saved: {len(saved_files)}")
    print(f"  Total Records  : {total_records}")
    print(f"  Skipped        : {len(skipped)} localities")
    print(f"  Finished At    : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if skipped:
        print(f"\n  Skipped Localities:")
        for s in skipped:
            print(f"    - {s}")
    print("=" * 60)


if __name__ == "__main__":
    main()