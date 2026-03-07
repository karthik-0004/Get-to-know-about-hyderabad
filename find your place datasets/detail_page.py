"""
Inspects a single property DETAIL page to find floors/balcony fields.
Run: python inspect_detail_page.py
"""
from playwright.sync_api import sync_playwright
import time

# We'll click the first property card and inspect its detail page
LISTING_URL = "https://housing.com/in/buy/hyderabad/house-bandlaguda"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=50)
    page = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
        viewport={"width": 1400, "height": 900}
    ).new_page()

    print("Loading IH listing page...")
    page.goto(LISTING_URL, timeout=50000, wait_until="domcontentloaded")
    time.sleep(4)

    # Get the first property detail link
    detail_url = page.evaluate("""
        () => {
            const cards = document.querySelectorAll('article');
            for (const card of cards) {
                const link = card.querySelector('a[href*="/in/buy/"]');
                if (link) return link.getAttribute('href');
            }
            return null;
        }
    """)

    if detail_url:
        full_url = "https://housing.com" + detail_url if detail_url.startswith("/") else detail_url
        print(f"Opening detail page: {full_url}")
        page.goto(full_url, timeout=50000, wait_until="domcontentloaded")
        time.sleep(4)
        for pct in [0.3, 0.6, 1.0]:
            page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {pct})")
            time.sleep(0.8)

        print("\n=== FULL PAGE TEXT (first 3000 chars) ===")
        txt = page.inner_text("body")
        print(txt[:3000])

        print("\n=== SEARCHING FOR floor/balcony/storey FIELDS ===")
        result = page.evaluate("""
            () => {
                const found = [];
                document.querySelectorAll('*').forEach(el => {
                    const txt = (el.innerText || '').toLowerCase().trim();
                    if ((txt.includes('floor') || txt.includes('balcon') ||
                         txt.includes('storey') || txt.includes('storied') ||
                         txt.includes('g+') || txt.includes('no. of'))
                        && txt.length < 150 && el.children.length <= 4) {
                        found.push({
                            tag: el.tagName,
                            cls: el.className.substring(0,60),
                            txt: el.innerText.trim().substring(0,120)
                        });
                    }
                });
                return found.slice(0, 30);
            }
        """)
        for r in result:
            print(f"  <{r['tag']}> class='{r['cls']}'")
            print(f"    → '{r['txt']}'")

        print("\n=== ALL KEY-VALUE PAIRS ON PAGE (label: value) ===")
        pairs = page.evaluate("""
            () => {
                const results = [];
                // Look for definition list style pairs
                document.querySelectorAll('dt, th, [class*="label"], [class*="Label"], [class*="key"], [class*="Key"]').forEach(el => {
                    const label = el.innerText.trim();
                    const next = el.nextElementSibling;
                    const value = next ? next.innerText.trim() : '';
                    if (label && label.length < 50) {
                        results.push(label + ': ' + value);
                    }
                });
                return results.slice(0, 40);
            }
        """)
        for p_item in pairs:
            print(f"  {p_item}")

    input("\nPress ENTER to close...")
    browser.close()