"""
Run this FIRST to inspect housing.com's actual HTML structure.
It will print out what selectors work and save a snapshot of the page HTML.

    pip install playwright
    playwright install chromium
    python inspect_housing.py
"""

from playwright.sync_api import sync_playwright
import time

BASE_URL = "https://housing.com/price-trends/property-rates-for-buy-in-hyderabad_telangana-P679xe73u28050522"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=100)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 900}
    )
    page = context.new_page()

    print("Loading price trends page...")
    page.goto(BASE_URL, timeout=60000, wait_until="domcontentloaded")
    time.sleep(5)  # extra wait for JS to render the table

    # Scroll to load everything
    page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.5)")
    time.sleep(1)
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(2)

    # Save full HTML
    html = page.content()
    with open("page_snapshot.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Saved page_snapshot.html - open this in browser to inspect elements")

    # Try to find table rows
    print("\n--- Trying selectors ---")
    
    selectors_to_try = [
        "table tbody tr",
        "tr",
        "[class*='row']",
        "[class*='Row']",
        "[class*='locality']",
        "[class*='Locality']",
        "[class*='table']",
        "[class*='Table']",
        "[class*='list']",
        "div > div > div > div",
    ]

    for sel in selectors_to_try:
        els = page.query_selector_all(sel)
        if els:
            print(f"  ✔ '{sel}' → {len(els)} elements")
            # Print first element's text
            try:
                txt = els[0].inner_text().strip()[:100]
                print(f"     First: {repr(txt)}")
            except:
                pass
        else:
            print(f"  ✗ '{sel}' → 0")

    # Try to find any element containing "Miyapur"
    print("\n--- Looking for 'Miyapur' text ---")
    try:
        el = page.query_selector("text=Miyapur")
        if el:
            parent = el.evaluate("el => el.parentElement.outerHTML")
            print("Parent HTML:", parent[:500])
            grandparent = el.evaluate("el => el.parentElement.parentElement.outerHTML")
            print("Grandparent HTML:", grandparent[:500])
    except Exception as e:
        print(f"Error: {e}")

    # Print all classes that appear in the page
    print("\n--- All unique class names containing 'row', 'table', 'locality', 'price' ---")
    all_classes = page.evaluate("""
        () => {
            const classes = new Set();
            document.querySelectorAll('*').forEach(el => {
                el.classList.forEach(c => {
                    if (/row|table|locality|price|list|card/i.test(c)) {
                        classes.add(c);
                    }
                });
            });
            return [...classes];
        }
    """)
    for c in sorted(all_classes):
        print(f"  .{c}")

    input("\nPress ENTER to close browser...")
    browser.close()

print("\nDone! Check page_snapshot.html and the printed selectors above.")
print("Share the output with Claude to fix the scraper.")