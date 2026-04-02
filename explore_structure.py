"""
Quick exploration script to inspect jawa.gg HTML structure
before building the full scraper.
"""

import asyncio
from playwright.async_api import async_playwright


ACTIVE_URL = "https://www.jawa.gg/gaming-pcs"
SHOP_URL = "https://www.jawa.gg/shop/full-systems/gaming-pcs-0V1FT57L"
SOLD_URL = "https://www.jawa.gg/shop/full-systems/gaming-pcs-show-sold~5c456b-7fa58"


async def explore():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            executable_path="/root/.cache/ms-playwright/chromium-1194/chrome-linux/chrome",
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()

        for label, url in [("ACTIVE (/gaming-pcs)", ACTIVE_URL), ("SHOP (gaming-pcs-0V1FT57L)", SHOP_URL), ("SOLD", SOLD_URL)]:
            print(f"\n{'='*60}")
            print(f"  Fetching: {label}")
            print(f"  URL: {url}")
            print(f"{'='*60}")
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(3000)

                final_url = page.url
                print(f"  Final URL after redirect: {final_url}")

                # Page title
                title = await page.title()
                print(f"  Page title: {title}")

                # Count listing cards via various candidate selectors
                candidates = [
                    "article",
                    "[class*='listing']",
                    "[class*='product']",
                    "[class*='card']",
                    "[data-listing-id]",
                    "[data-product-id]",
                    "li[class*='item']",
                    "div[class*='grid'] > div",
                    "a[href*='/listings/']",
                    "a[href*='/item/']",
                    "a[href*='/p/']",
                ]
                print("\n  -- Listing card candidates --")
                for sel in candidates:
                    count = await page.locator(sel).count()
                    if count > 0:
                        print(f"    {sel!r:40s} → {count} elements")

                # Dump the outer HTML of the first plausible listing
                print("\n  -- First <article> outer HTML (if any) --")
                art_count = await page.locator("article").count()
                if art_count:
                    html = await page.locator("article").first.inner_html()
                    print(html[:3000])
                else:
                    # Fall back to a[href*='/'] cards
                    print("  (no <article> tags; trying a[href*='/listings/'] …)")
                    link_count = await page.locator("a[href*='/listings/']").count()
                    if link_count:
                        html = await page.locator("a[href*='/listings/']").first.inner_html()
                        print(html[:3000])
                    else:
                        # Last resort: dump body snippet
                        body = await page.locator("body").inner_html()
                        print("  (Dumping first 3000 chars of body)")
                        print(body[:3000])

                # Pagination
                print("\n  -- Pagination candidates --")
                pag_candidates = [
                    "[class*='pagination']",
                    "[class*='pager']",
                    "nav[aria-label*='page']",
                    "button[aria-label*='next']",
                    "a[rel='next']",
                ]
                for sel in pag_candidates:
                    count = await page.locator(sel).count()
                    if count > 0:
                        html = await page.locator(sel).first.inner_html()
                        print(f"  {sel!r}: {html[:400]}")

            except Exception as e:
                print(f"  ERROR: {e}")

        await browser.close()
        print("\n\nDone exploring.")


asyncio.run(explore())
