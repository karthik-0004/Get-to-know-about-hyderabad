"""
Inspects a single Independent House card to find floors/balcony fields.
Run: python inspect_ih_card.py
"""
from playwright.sync_api import sync_playwright
import time

URL = "https://housing.com/in/buy/hyderabad/house-bandlaguda"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=50)
    page = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
        viewport={"width": 1400, "height": 900}
    ).new_page()

    print("Loading IH listing page...")
    page.goto(URL, timeout=50000, wait_until="domcontentloaded")
    time.sleep(4)
    for pct in [0.3, 0.6, 1.0]:
        page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {pct})")
        time.sleep(0.8)

    print("\n=== FULL TEXT OF FIRST 3 ARTICLE CARDS ===")
    cards = page.query_selector_all("article")
    print(f"Total cards: {len(cards)}")
    for i, card in enumerate(cards[:3]):
        print(f"\n--- Card {i+1} ---")
        print(card.inner_text().strip())
        print(f"\n--- Card {i+1} HTML (first 1000 chars) ---")
        print(card.inner_html()[:1000])

    print("\n=== SEARCHING FOR 'floor', 'balcony', 'storey' TEXT ===")
    result = page.evaluate("""
        () => {
            const found = [];
            document.querySelectorAll('*').forEach(el => {
                const txt = (el.innerText || '').toLowerCase();
                if ((txt.includes('floor') || txt.includes('balcony') || 
                     txt.includes('storey') || txt.includes('storied')) 
                    && txt.length < 200 && el.children.length <= 3) {
                    found.push({
                        tag: el.tagName,
                        cls: el.className.substring(0,60),
                        txt: el.innerText.trim().substring(0,100)
                    });
                }
            });
            return found.slice(0, 20);
        }
    """)
    for r in result:
        print(f"  <{r['tag']}> class='{r['cls']}' → '{r['txt']}'")

    input("\nPress ENTER to close...")
    browser.close()