"""
Inspects the actual property listing page HTML for Miyapur.
Run: python inspect_listings.py
Then share the output with Claude.
"""

from playwright.sync_api import sync_playwright
import time

URL = "https://housing.com/in/buy/hyderabad/miyapur"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=50)
    page = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        viewport={"width": 1400, "height": 900}
    ).new_page()

    print("Loading Miyapur listings page...")
    page.goto(URL, timeout=50000, wait_until="domcontentloaded")
    time.sleep(5)

    # Scroll to load cards
    for pct in [0.3, 0.6, 1.0]:
        page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {pct})")
        time.sleep(1)

    # Save full HTML
    html = page.content()
    with open("listings_snapshot.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Saved listings_snapshot.html")

    # Find element containing price like ₹68L or BHK
    print("\n--- Looking for a property card with BHK text ---")
    el = page.query_selector("text=BHK")
    if el:
        # Walk up to find the card container
        for level in range(1, 6):
            try:
                ancestor = el.evaluate(f"""
                    el => {{
                        let node = el;
                        for(let i=0; i<{level}; i++) node = node.parentElement;
                        return {{
                            tag: node.tagName,
                            classes: node.className,
                            text: node.innerText.slice(0, 300)
                        }};
                    }}
                """)
                print(f"Level {level} parent → tag={ancestor['tag']} class={ancestor['classes']!r}")
                print(f"   Text: {ancestor['text']!r}")
                print()
            except:
                break
    else:
        print("No 'BHK' text found on page!")

    # Print all unique class names on the page
    print("\n--- All class names containing: card, srp, listing, property, result, item ---")
    classes = page.evaluate("""
        () => {
            const s = new Set();
            document.querySelectorAll('*').forEach(el => {
                el.classList.forEach(c => {
                    if (/card|srp|listing|property|result|item|flat|proj/i.test(c)) s.add(c);
                });
            });
            return [...s];
        }
    """)
    for c in sorted(classes):
        print(f"  .{c}")

    # Count how many elements match each selector
    print("\n--- Selector counts ---")
    test_selectors = [
        "div[data-testid='srp-card']",
        "[data-testid*='card']",
        "[data-testid*='listing']",
        "[data-testid*='property']",
        "div[class*='srpCard']",
        "div[class*='card']",
        "div[class*='Card']",
        "div[class*='listing']",
        "div[class*='Listing']",
        "div[class*='property']",
        "div[class*='Property']",
        "div[class*='result']",
        "div[class*='item']",
        "div[class*='Item']",
        "article",
        "li[class*='card']",
        "li[class*='item']",
    ]
    for sel in test_selectors:
        els = page.query_selector_all(sel)
        if els:
            txt = ""
            try:
                txt = els[0].inner_text().strip()[:80].replace("\n", " ")
            except:
                pass
            print(f"  ✔ {sel!r:45} → {len(els):3}   first: {txt!r}")
        else:
            print(f"  ✗ {sel!r:45} → 0")

    input("\nPress ENTER to close...")
    browser.close()