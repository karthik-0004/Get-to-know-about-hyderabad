# hyderabad_housing_scraper.py

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
from datetime import datetime
import os

# ─────────────────────────────────────────────
# MAIN FOLDER ON DESKTOP
# ─────────────────────────────────────────────
DESKTOP_PATH    = os.path.join(os.path.expanduser("~"), "Desktop")
MAIN_FOLDER     = os.path.join(DESKTOP_PATH, "Hyderabad_Housing_Data")
os.makedirs(MAIN_FOLDER, exist_ok=True)

# ─────────────────────────────────────────────
# ALL HYDERABAD LOCALITIES
# ─────────────────────────────────────────────
LOCALITIES = [
    # Central Hyderabad
    "Abids", "Basheerbagh", "Lakdikapul", "Khairatabad",
    "Himayatnagar", "Narayanaguda", "Chikkadpally", "RTC X Roads",
    "Musheerabad", "Koti", "Chaderghat", "Malakpet", "Amberpet",
    "Bagh Amberpet", "Vidyanagar", "Ram Nagar", "Sultan Bazar",
    "Masab Tank",

    # Secunderabad & North
    "Secunderabad", "Begumpet", "Trimulgherry", "Alwal",
    "Bowenpally", "Old Bowenpally", "Tarnaka", "Malkajgiri",
    "Sainikpuri", "ECIL", "Kapra", "Dammaiguda", "Kompally",
    "Medchal", "Shamirpet", "Jeedimetla", "Suchitra", "Quthbullapur",

    # West Hyderabad
    "Kukatpally", "KPHB Colony", "Miyapur", "Bachupally",
    "Nizampet", "Pragathi Nagar", "Hydernagar", "Moosapet",
    "Erragadda", "Sanath Nagar", "Balanagar", "Chintal",
    "Gajularamaram", "Suraram", "Patancheru", "Beeramguda", "Ameenpur",

    # IT & Financial Corridor
    "Madhapur", "Hitech City", "Gachibowli", "Kondapur",
    "Manikonda", "Puppalguda", "Nallagandla", "Tellapur",
    "Narsingi", "Kokapet", "Financial District", "Nanakramguda",
    "Raidurg", "Khanamet", "Gowlidoddy", "Gopanpally",
    "Serilingampally", "Hafeezpet", "Madinaguda", "Lingampally",

    # Premium Areas
    "Banjara Hills", "Jubilee Hills", "Film Nagar",
    "Shaikpet", "Tolichowki", "Srinagar Colony", "Yousufguda",

    # South Hyderabad
    "Mehdipatnam", "Attapur", "Rajendranagar", "Bandlaguda Jagir",
    "Upparpally", "Kismatpur", "Gudimalkapur",
    "Asif Nagar", "Red Hills",

    # East Hyderabad
    "LB Nagar", "Dilsukhnagar", "Nagole", "Uppal", "Habsiguda",
    "Nacharam", "Moula Ali", "Boduppal", "Peerzadiguda",
    "Medipally", "Pocharam", "Ghatkesar", "Hayathnagar",
    "Vanastalipuram", "Champapet", "Saroornagar", "Karmanghat",
    "Badangpet", "Meerpet",

    # Old City
    "Charminar", "Falaknuma", "Bahadurpura", "Yakutpura",
    "Chandrayangutta", "Santoshnagar", "Dabeerpura", "Katedan",

    # Airport & Outskirts
    "Shamshabad", "Adibatla", "Maheshwaram", "Kandukur",
    "Ibrahimpatnam", "Balapur", "Shadnagar",
    "Turkapally", "Bibinagar",
]


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
# EXTRACT LISTINGS FROM PAGE
# ─────────────────────────────────────────────
def extract_listings(soup, locality):
    properties = []

    cards = soup.select(
        "div.card-container, "
        "div[class*='property-card'], "
        "div[class*='listing'], "
        "div[class*='proj-card'], "
        "li[class*='property'], "
        "div[class*='card']"
    )

    for card in cards:
        # Project Name
        name = (
            card.select_one("h2")
            or card.select_one("h3")
            or card.select_one("[class*='project-name']")
            or card.select_one("[class*='prop-name']")
            or card.select_one("[class*='title']")
            or card.select_one("[class*='name']")
        )

        # Price
        price = (
            card.select_one("[class*='price']")
            or card.select_one("[class*='cost']")
            or card.select_one("[class*='amount']")
        )

        # Area / SqFt
        area = (
            card.select_one("[class*='area']")
            or card.select_one("[class*='sqft']")
            or card.select_one("[class*='sq-ft']")
            or card.select_one("[class*='size']")
            or card.select_one("[class*='carpet']")
            or card.select_one("[class*='super']")
            or card.select_one("span:-soup-contains('Sq.Ft')")
            or card.select_one("span:-soup-contains('sq ft')")
            or card.select_one("span:-soup-contains('sqft')")
            or card.select_one("li:-soup-contains('Sq.Ft')")
        )

        # BHK
        bhk = (
            card.select_one("[class*='bhk']")
            or card.select_one("[class*='bedroom']")
            or card.select_one("[class*='bed']")
            or card.select_one("[class*='config']")
            or card.select_one("[class*='room']")
            or card.select_one("span:-soup-contains('BHK')")
            or card.select_one("li:-soup-contains('BHK')")
            or card.select_one("span:-soup-contains('Bedroom')")
        )

        # Property Type
        ptype = (
            card.select_one("[class*='property-type']")
            or card.select_one("[class*='prop-type']")
            or card.select_one("[class*='type']")
            or card.select_one("span:-soup-contains('Apartment')")
            or card.select_one("span:-soup-contains('Villa')")
            or card.select_one("span:-soup-contains('House')")
            or card.select_one("span:-soup-contains('Flat')")
            or card.select_one("li:-soup-contains('Apartment')")
            or card.select_one("li:-soup-contains('Villa')")
        )

        # Price per SqFt
        psqft = (
            card.select_one("[class*='per-sqft']")
            or card.select_one("[class*='sqft-price']")
            or card.select_one("[class*='price-sqft']")
            or card.select_one("span:-soup-contains('/ Sq.Ft')")
            or card.select_one("span:-soup-contains('/sqft')")
            or card.select_one("span:-soup-contains('per sqft')")
        )

        # Locality
        loc_el = (
            card.select_one("[class*='locality']")
            or card.select_one("[class*='location']")
            or card.select_one("[class*='address']")
            or card.select_one("[class*='area-name']")
        )

        # Furnishing
        furnish = (
            card.select_one("[class*='furnish']")
            or card.select_one("span:-soup-contains('Furnished')")
            or card.select_one("span:-soup-contains('Unfurnished')")
        )

        # Bathrooms
        bath = (
            card.select_one("[class*='bath']")
            or card.select_one("[class*='bathroom']")
            or card.select_one("span:-soup-contains('Bath')")
            or card.select_one("li:-soup-contains('Bath')")
        )

        # Skip cards with no useful data
        if not any([name, price, area, bhk]):
            continue

        # Clean up text
        def txt(el):
            return " ".join(el.get_text(strip=True).split()) if el else "N/A"

        properties.append({
            "Locality":      txt(loc_el) if loc_el else locality,
            "City":          "Hyderabad",
            "Project Name":  txt(name),
            "Price (INR)":   txt(price),
            "Price/SqFt":    txt(psqft),
            "Area (SqFt)":   txt(area),
            "BHK":           txt(bhk),
            "Bathrooms":     txt(bath),
            "Property Type": txt(ptype),
            "Furnishing":    txt(furnish),
            "Source":        "squareyards.com",
            "Scraped At":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

    return properties


# ─────────────────────────────────────────────
# SCRAPE ONE LOCALITY
# ─────────────────────────────────────────────
def scrape_locality(driver, locality):
    slug = locality.lower().replace(" ", "-")
    url  = f"https://www.squareyards.com/sale/property-for-sale-in-{slug}-hyderabad"

    try:
        driver.get(url)
        time.sleep(random.uniform(4, 6))

        page_text = driver.page_source.lower()

        # ── Skip if no results found ──
        no_result_phrases = [
            "no properties found",
            "no results found",
            "0 properties",
            "couldn't find",
            "no listing",
            "no property found",
            "currently no properties",
            "we couldn't find",
        ]
        if any(phrase in page_text for phrase in no_result_phrases):
            print(f"    [SKIP] No listings found for {locality}.")
            return []

        # Scroll to load all cards
        for _ in range(5):
            driver.execute_script("window.scrollBy(0, window.innerHeight);")
            time.sleep(random.uniform(0.8, 1.2))

        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)

        soup     = BeautifulSoup(driver.page_source, "html.parser")
        listings = extract_listings(soup, locality)

        return listings

    except Exception as e:
        print(f"    [ERROR] {locality}: {e}")
        return []


# ─────────────────────────────────────────────
# SAVE ONE LOCALITY CSV
# ─────────────────────────────────────────────
def save_locality_csv(df, locality):
    # Clean filename — remove special characters
    safe_name = locality.replace(" ", "_").replace("/", "_")
    filename  = f"{safe_name}.csv"
    filepath  = os.path.join(MAIN_FOLDER, filename)

    df.to_csv(filepath, index=False, encoding="utf-8-sig")
    return filepath


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  Hyderabad Housing Data Scraper")
    print("=" * 60)
    print(f"  Started At     : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Total Localities: {len(LOCALITIES)}")
    print(f"  Saving To      : {MAIN_FOLDER}")
    print("=" * 60)

    driver = create_driver()
    print("\n  [OK] Browser launched.\n")

    saved_files   = []
    skipped       = []
    failed        = []
    total_records = 0

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

            # Remove rows where Price, Area and BHK are all N/A
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
                print(f"           → Skipped (all rows were empty after cleaning)")
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
    print(f"  Skipped        : {len(skipped)} localities (no data)")
    print(f"  Finished At    : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if skipped:
        print(f"\n  Skipped Localities:")
        for s in skipped:
            print(f"    - {s}")

    print("\n  Saved CSVs:")
    for f in saved_files:
        print(f"    ✓ {os.path.basename(f)}")

    print("=" * 60)


if __name__ == "__main__":
    main()
