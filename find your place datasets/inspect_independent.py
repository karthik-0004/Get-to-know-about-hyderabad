"""
Inspects the Property Type filter dropdown on housing.com listing page.
Run: python inspect_filter.py
Share the output with Claude.
"""
from playwright.sync_api import sync_playwright
import time

URL = "https://housing.com/in/buy/hyderabad/bandlaguda"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=80)
    page = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
        viewport={"width": 1400, "height": 900}
    ).new_page()

    print("Loading listing page...")
    page.goto(URL, timeout=50000, wait_until="domcontentloaded")
    time.sleep(4)

    # Save snapshot
    html = page.content()
    with open("filter_snapshot.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Saved filter_snapshot.html\n")

    # Print all top filter buttons/pills
    print("=== ALL FILTER BUTTONS AT TOP ===")
    filters = page.evaluate("""
        () => {
            const results = [];
            document.querySelectorAll('*').forEach(el => {
                const txt = el.innerText ? el.innerText.trim() : '';
                const tag = el.tagName;
                const cls = el.className || '';
                if (
                    txt.length < 40 && txt.length > 1 &&
                    el.children.length <= 2 &&
                    (cls.includes('filter') || cls.includes('Filter') ||
                     cls.includes('pill') || cls.includes('Pill') ||
                     cls.includes('chip') || cls.includes('Chip') ||
                     cls.includes('dropdown') || cls.includes('Dropdown') ||
                     txt === 'Property Type' || txt === 'BHK Type' ||
                     txt === 'Sale Type' || txt.startsWith('Independent'))
                ) {
                    results.push({tag, cls: cls.substring(0,60), txt});
                }
            });
            return results.slice(0, 30);
        }
    """)
    for f in filters:
        print(f"  <{f['tag']}> class='{f['cls']}' text='{f['txt']}'")

    print("\n=== CLICKING 'Property Type' BUTTON ===")
    # Try clicking it
    clicked = page.evaluate("""
        () => {
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
            let node;
            while (node = walker.nextNode()) {
                const txt = node.textContent.trim();
                if (txt === 'Property Type') {
                    const p = node.parentElement;
                    p.click();
                    return {tag: p.tagName, cls: p.className, html: p.outerHTML.substring(0,200)};
                }
            }
            return null;
        }
    """)
    print(f"Clicked: {clicked}")
    time.sleep(2)

    print("\n=== DROPDOWN OPTIONS AFTER CLICK ===")
    options = page.evaluate("""
        () => {
            const results = [];
            document.querySelectorAll('input[type=checkbox], label').forEach(el => {
                const txt = el.innerText || el.value || '';
                if (txt.trim()) results.push({
                    tag: el.tagName,
                    type: el.type || '',
                    id: el.id || '',
                    cls: (el.className || '').substring(0,60),
                    txt: txt.trim().substring(0,50),
                    checked: el.checked || false
                });
            });
            return results;
        }
    """)
    for o in options:
        print(f"  <{o['tag']} type={o['type']}> id='{o['id']}' checked={o['checked']} text='{o['txt']}'")

    print("\n=== LOOKING FOR 'Independent House' IN DROPDOWN ===")
    ih = page.evaluate("""
        () => {
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
            let node;
            const found = [];
            while (node = walker.nextNode()) {
                if (node.textContent.trim() === 'Independent House') {
                    const p = node.parentElement;
                    const gp = p.parentElement;
                    found.push({
                        parent_tag: p.tagName,
                        parent_cls: p.className,
                        parent_html: p.outerHTML.substring(0, 300),
                        gp_tag: gp.tagName,
                        gp_cls: gp.className,
                    });
                }
            }
            return found;
        }
    """)
    for item in ih:
        print(f"\n  parent: <{item['parent_tag']}> class='{item['parent_cls']}'")
        print(f"  gp:     <{item['gp_tag']}> class='{item['gp_cls']}'")
        print(f"  html:   {item['parent_html']}")

    input("\nPress ENTER to close...")
    browser.close()