"""
jawa.gg Gaming PC Scraper
=========================
Scrapes active and sold Gaming PC listings from jawa.gg and saves
results to jawa_listings.csv.

Usage
-----
    python jawa_scraper.py               # normal run
    python jawa_scraper.py --debug       # dump raw HTML for selector inspection
    python jawa_scraper.py --sold-only   # only scrape sold listings
    python jawa_scraper.py --active-only # only scrape active listings
    python jawa_scraper.py --max-pages 3 # limit pages per section (useful for testing)
"""

import asyncio
import csv
import json
import random
import re
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright, Page, BrowserContext
from playwright_stealth import Stealth

from normalize import normalize_gpu, normalize_cpu, extract_ram_gb, extract_storage


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CHROMIUM_PATH = Path.home() / ".cache/ms-playwright/chromium-1194/chrome-linux/chrome"

ACTIVE_URL = "https://www.jawa.gg/gaming-pcs"
SOLD_URL   = "https://www.jawa.gg/shop/full-systems/gaming-pcs-show-sold~5c456b-7fa58"

OUTPUT_CSV = Path("jawa_listings.csv")

CSV_FIELDS = [
    "title",
    "price",
    "gpu",
    "cpu",
    "ram_gb",
    "storage",
    "status",
    "url",
    "date_sold",
    "date_listed",
    "date_scraped",
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def random_delay(lo: float = 2.0, hi: float = 3.5) -> float:
    return random.uniform(lo, hi)


def parse_price(text: str) -> float | None:
    """Strip '$', commas, whitespace and return a float, or None."""
    cleaned = re.sub(r"[^\d.]", "", text.strip())
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_date(text: str | None) -> str | None:
    """Try to turn a messy date string into ISO-8601 (date only), or None."""
    if not text:
        return None
    text = text.strip()
    # Already looks like a date
    if re.match(r"\d{4}-\d{2}-\d{2}", text):
        return text[:10]
    # Month DD, YYYY  /  DD Month YYYY
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y",
                "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    # Relative like "2 days ago", "just now" — leave as-is
    if re.search(r"\bago\b|just now", text, re.IGNORECASE):
        return text
    return text or None


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Selector strategies
# ---------------------------------------------------------------------------

# Ordered list of CSS selectors to try when looking for listing cards.
# The first one that returns >= 1 elements wins.
CARD_SELECTORS = [
    # Semantic / data-attribute selectors (most reliable on JS-rendered sites)
    "[data-listing-id]",
    "[data-product-id]",
    "[data-testid='listing-card']",
    "[data-testid='product-card']",
    # Common class name fragments (React/Next.js sites often use these)
    "[class*='ListingCard']",
    "[class*='ProductCard']",
    "[class*='listing-card']",
    "[class*='product-card']",
    "[class*='ItemCard']",
    "[class*='item-card']",
    # Anchor-based — jawa often wraps each card in an <a>
    "a[href*='/listings/']",
    "a[href*='/item/']",
    "a[href*='/p/']",
    # Grid children fallback
    "main article",
    "article",
    # Last resort: any li that looks like a card
    "ul[class*='grid'] li",
    "ul[class*='list'] li",
]

PRICE_SELECTORS = [
    "[data-testid='price']",
    "[class*='price']",
    "[class*='Price']",
    "span[class*='amount']",
    "span[class*='cost']",
]

TITLE_SELECTORS = [
    "h1", "h2", "h3",
    "[class*='title']",
    "[class*='Title']",
    "[class*='name']",
    "[class*='Name']",
]

SPEC_SELECTORS = [
    "[class*='spec']",
    "[class*='Spec']",
    "[class*='detail']",
    "[class*='Detail']",
    "[class*='description']",
    "[class*='Description']",
    "ul",
    "dl",
]

DATE_SELECTORS = [
    "[class*='date']",
    "[class*='Date']",
    "time",
    "[datetime]",
]

PAGINATION_SELECTORS = [
    "a[aria-label*='Next']",
    "a[aria-label*='next']",
    "button[aria-label*='Next']",
    "button[aria-label*='next']",
    "[class*='pagination'] a:last-child",
    "[class*='Pagination'] a:last-child",
    "a[rel='next']",
    "nav a:last-child",
]


# ---------------------------------------------------------------------------
# Single card / single listing-page parsing
# ---------------------------------------------------------------------------

async def _text(locator, default: str = "") -> str:
    """Safely get inner text from a locator."""
    try:
        count = await locator.count()
        if count:
            return (await locator.first.inner_text()).strip()
    except Exception:
        pass
    return default


async def _attr(locator, attr: str, default: str = "") -> str:
    try:
        count = await locator.count()
        if count:
            val = await locator.first.get_attribute(attr)
            return (val or "").strip()
    except Exception:
        pass
    return default


async def extract_from_card(card, base_url: str, status: str) -> dict:
    """
    Given a Playwright locator pointing to a single listing card,
    extract all available fields.  Falls back gracefully on missing elements.
    """
    scraped = now_iso()
    result: dict = {f: None for f in CSV_FIELDS}
    result["status"] = status
    result["date_scraped"] = scraped

    # --- URL ---
    href = await _attr(card.locator("a").first, "href")
    if not href:
        # Maybe the card itself is an <a>
        href = await _attr(card, "href")
    if href:
        result["url"] = href if href.startswith("http") else f"https://www.jawa.gg{href}"

    # --- Title ---
    for sel in TITLE_SELECTORS:
        txt = await _text(card.locator(sel))
        if txt:
            result["title"] = txt
            break
    if not result["title"]:
        # Use the full text of the card as a last resort
        result["title"] = (await _text(card))[:200] or None

    # --- Price ---
    for sel in PRICE_SELECTORS:
        txt = await _text(card.locator(sel))
        if txt and "$" in txt:
            result["price"] = parse_price(txt)
            break
    if result["price"] is None:
        # Scan all text for a price-like pattern
        full_text = await _text(card)
        m = re.search(r"\$\s*([\d,]+(?:\.\d{2})?)", full_text)
        if m:
            result["price"] = parse_price(m.group(1))

    # --- Dates ---
    for sel in DATE_SELECTORS:
        loc = card.locator(sel)
        count = await loc.count()
        for i in range(count):
            item = loc.nth(i)
            txt = await _text(item)
            dt_attr = await _attr(item, "datetime")
            date_str = parse_date(dt_attr or txt)
            if date_str:
                lbl = (await _text(item.locator(".."))[:50]).lower()
                if status == "sold" and result["date_sold"] is None:
                    result["date_sold"] = date_str
                elif result["date_listed"] is None:
                    result["date_listed"] = date_str

    # --- Specs (GPU, CPU, RAM, Storage) from all visible text ---
    full_text = await _text(card)
    _fill_specs(result, full_text)

    return result


def _fill_specs(result: dict, text: str) -> None:
    """Fill GPU/CPU/RAM/storage fields from raw text if not already set."""
    if not result.get("gpu"):
        result["gpu"] = normalize_gpu(text)
    if not result.get("cpu"):
        result["cpu"] = normalize_cpu(text)
    if not result.get("ram_gb"):
        result["ram_gb"] = extract_ram_gb(text)
    if not result.get("storage"):
        result["storage"] = extract_storage(text)


# ---------------------------------------------------------------------------
# Per-listing-page deep scrape (used when card data is incomplete)
# ---------------------------------------------------------------------------

async def deep_scrape_listing(page: Page, url: str, status: str) -> dict:
    """
    Visit an individual listing page and extract full details.
    Returns a dict with all CSV_FIELDS.
    """
    scraped = now_iso()
    result: dict = {f: None for f in CSV_FIELDS}
    result["url"] = url
    result["status"] = status
    result["date_scraped"] = scraped

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(int(random_delay(1.5, 2.5) * 1000))

        # Title — usually in h1
        result["title"] = await _text(page.locator("h1").first) or None

        # Price
        for sel in PRICE_SELECTORS:
            txt = await _text(page.locator(sel))
            if txt and "$" in txt:
                result["price"] = parse_price(txt)
                break
        if result["price"] is None:
            m = re.search(r"\$\s*([\d,]+(?:\.\d{2})?)", await _text(page.locator("body")))
            if m:
                result["price"] = parse_price(m.group(1))

        # Dates
        for sel in DATE_SELECTORS:
            loc = page.locator(sel)
            count = await loc.count()
            for i in range(count):
                item = loc.nth(i)
                dt_attr = await _attr(item, "datetime")
                txt = await _text(item)
                date_str = parse_date(dt_attr or txt)
                if date_str:
                    if status == "sold" and result["date_sold"] is None:
                        result["date_sold"] = date_str
                    elif result["date_listed"] is None:
                        result["date_listed"] = date_str

        # Specs from page body
        body_text = await _text(page.locator("body"))
        _fill_specs(result, body_text)

        # Also try JSON-LD structured data
        scripts = page.locator("script[type='application/ld+json']")
        count = await scripts.count()
        for i in range(count):
            try:
                raw = await scripts.nth(i).inner_text()
                data = json.loads(raw)
                _extract_jsonld(result, data)
            except Exception:
                pass

    except Exception as e:
        print(f"  [warn] deep_scrape failed for {url}: {e}")

    return result


def _extract_jsonld(result: dict, data: dict | list) -> None:
    """Pull fields from JSON-LD structured data if present."""
    if isinstance(data, list):
        for item in data:
            _extract_jsonld(result, item)
        return
    if not isinstance(data, dict):
        return

    if not result.get("title"):
        result["title"] = data.get("name") or data.get("headline")
    if result.get("price") is None:
        offers = data.get("offers") or data.get("Offers")
        if isinstance(offers, dict):
            p = offers.get("price") or offers.get("lowPrice")
            if p is not None:
                result["price"] = parse_price(str(p))
    desc = data.get("description") or ""
    if desc:
        _fill_specs(result, desc)


# ---------------------------------------------------------------------------
# Core pagination loop
# ---------------------------------------------------------------------------

async def find_card_selector(page: Page) -> str | None:
    """Try each candidate selector; return the first that finds >=2 elements."""
    for sel in CARD_SELECTORS:
        try:
            count = await page.locator(sel).count()
            if count >= 2:
                return sel
        except Exception:
            pass
    return None


async def get_next_page_url(page: Page) -> str | None:
    """Return the URL of the next page, or None if we're on the last page."""
    for sel in PAGINATION_SELECTORS:
        try:
            loc = page.locator(sel)
            count = await loc.count()
            if count:
                href = await loc.first.get_attribute("href")
                if href:
                    return href if href.startswith("http") else f"https://www.jawa.gg{href}"
                # Some pagination is button-click based; check disabled state
                disabled = await loc.first.get_attribute("disabled")
                aria_disabled = await loc.first.get_attribute("aria-disabled")
                if disabled or aria_disabled == "true":
                    return None
        except Exception:
            pass
    return None


async def scrape_section(
    context: BrowserContext,
    start_url: str,
    status: str,
    max_pages: int | None,
    debug: bool,
) -> list[dict]:
    """
    Scrape all pages of one section (active or sold).
    Returns list of listing dicts.
    """
    listings: list[dict] = []
    page = await context.new_page()
    url = start_url
    page_num = 0

    while url:
        page_num += 1
        if max_pages and page_num > max_pages:
            print(f"  [info] Reached --max-pages limit ({max_pages}), stopping.")
            break

        print(f"\n[{'ACTIVE' if status == 'active' else 'SOLD':6}] Page {page_num}: {url}")

        try:
            await page.goto(url, wait_until="networkidle", timeout=45_000)
        except Exception as e:
            print(f"  [warn] networkidle timed out ({e}); trying domcontentloaded…")
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            except Exception as e2:
                print(f"  [error] Failed to load page: {e2}")
                break

        # Extra wait for JS rendering
        await page.wait_for_timeout(int(random_delay(2.0, 3.5) * 1000))

        if debug:
            dump_path = Path(f"debug_{status}_page{page_num}.html")
            dump_path.write_text(await page.content(), encoding="utf-8")
            print(f"  [debug] HTML dumped to {dump_path}")

        # Find which selector works for cards on this page
        card_sel = await find_card_selector(page)
        if not card_sel:
            print("  [warn] No listing cards found on this page. "
                  "Run with --debug to inspect the HTML.")
            break

        cards = page.locator(card_sel)
        total_cards = await cards.count()
        print(f"  Found {total_cards} cards using selector: {card_sel!r}")

        page_listings: list[dict] = []
        for i in range(total_cards):
            card = cards.nth(i)
            try:
                listing = await extract_from_card(card, url, status)

                # If we couldn't get specs from the card, do a deep scrape
                needs_deep = (
                    listing.get("url")
                    and not any([listing.get("gpu"), listing.get("cpu"),
                                 listing.get("ram_gb"), listing.get("storage")])
                )
                if needs_deep and listing["url"]:
                    detail_page = await context.new_page()
                    try:
                        deep = await deep_scrape_listing(detail_page, listing["url"], status)
                        # Merge: deep values fill gaps from card parse
                        for field in CSV_FIELDS:
                            if not listing.get(field) and deep.get(field):
                                listing[field] = deep[field]
                    finally:
                        await detail_page.close()
                    await asyncio.sleep(random_delay())

                page_listings.append(listing)

                total_so_far = len(listings) + len(page_listings)
                print(f"  Scraped listing {total_so_far}: "
                      f"{(listing.get('title') or 'untitled')[:60]}")

            except Exception as e:
                print(f"  [error] Skipping card {i+1}/{total_cards}: {e}")

        listings.extend(page_listings)

        # Pagination
        next_url = await get_next_page_url(page)
        if next_url and next_url != url:
            url = next_url
            await asyncio.sleep(random_delay())
        else:
            break

    await page.close()
    return listings


# ---------------------------------------------------------------------------
# CSV output
# ---------------------------------------------------------------------------

def save_csv(listings: list[dict], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in listings:
            writer.writerow({k: row.get(k, "") for k in CSV_FIELDS})
    print(f"\nSaved {len(listings)} listings to {path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main(args: argparse.Namespace) -> None:
    chromium_path = CHROMIUM_PATH
    if not chromium_path.exists():
        # Let Playwright find whatever it has installed
        chromium_path = None  # type: ignore[assignment]

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            executable_path=str(chromium_path) if chromium_path else None,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-dev-shm-usage",
                "--disable-extensions",
                "--no-first-run",
                "--no-default-browser-check",
                "--window-size=1280,900",
            ],
        )

        user_agent = random.choice(USER_AGENTS)
        context = await browser.new_context(
            user_agent=user_agent,
            viewport={"width": 1280, "height": 900},
            locale="en-US",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
            },
        )

        # Apply comprehensive stealth patches to bypass Cloudflare bot detection
        await Stealth().apply_stealth_async(context)

        all_listings: list[dict] = []

        if not args.sold_only:
            print("\n=== Scraping ACTIVE listings ===")
            active = await scrape_section(
                context, ACTIVE_URL, "active", args.max_pages, args.debug
            )
            print(f"\nActive listings collected: {len(active)}")
            all_listings.extend(active)

        if not args.active_only:
            print("\n=== Scraping SOLD listings ===")
            sold = await scrape_section(
                context, SOLD_URL, "sold", args.max_pages, args.debug
            )
            print(f"\nSold listings collected: {len(sold)}")
            all_listings.extend(sold)

        await browser.close()

    print(f"\nTotal listings: {len(all_listings)}")
    if all_listings:
        save_csv(all_listings, OUTPUT_CSV)
    else:
        print("No listings found. Try running with --debug to inspect the page HTML.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="jawa.gg Gaming PC scraper")
    parser.add_argument("--debug", action="store_true",
                        help="Dump raw page HTML to files for selector inspection")
    parser.add_argument("--sold-only", action="store_true",
                        help="Only scrape sold listings")
    parser.add_argument("--active-only", action="store_true",
                        help="Only scrape active listings")
    parser.add_argument("--max-pages", type=int, default=None, metavar="N",
                        help="Stop after N pages per section (useful for testing)")
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
