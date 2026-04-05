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
    python jawa_scraper.py --clear-cookies # delete saved session cookies and start fresh
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

OUTPUT_CSV   = Path("jawa_listings.csv")
COOKIES_FILE = Path("jawa_cookies.json")

# Cloudflare challenge indicators
CF_TITLE_RE = re.compile(r"just a moment|checking your browser|attention required|ddos", re.I)
CF_URL_RE   = re.compile(r"/cdn-cgi/|cf-chl|challenge", re.I)

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
# Cookie persistence — avoids repeated CF challenges on subsequent runs
# ---------------------------------------------------------------------------

def load_cookies() -> list[dict]:
    if COOKIES_FILE.exists():
        try:
            return json.loads(COOKIES_FILE.read_text())
        except Exception:
            pass
    return []


def save_cookies(cookies: list[dict]) -> None:
    try:
        COOKIES_FILE.write_text(json.dumps(cookies, indent=2))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Cloudflare detection + waiting
# ---------------------------------------------------------------------------

async def is_cloudflare_challenge(page) -> bool:
    title = (await page.title()).strip()
    if CF_TITLE_RE.search(title):
        return True
    if CF_URL_RE.search(page.url):
        return True
    for sel in ["#cf-challenge-running", "#challenge-form",
                "[class*='cf-browser-verification']", "div#challenge-body"]:
        try:
            if await page.locator(sel).count():
                return True
        except Exception:
            pass
    return False


async def wait_for_cloudflare(page, timeout: int = 35) -> bool:
    """Wait up to *timeout* seconds for a CF JS challenge to auto-resolve."""
    print("  [CF] Challenge detected — waiting for auto-resolution…")
    for elapsed in range(timeout):
        await asyncio.sleep(1)
        if not await is_cloudflare_challenge(page):
            print(f"  [CF] Cleared after {elapsed + 1}s ✓")
            return True
    print(f"  [CF] Still blocked after {timeout}s — run --debug to inspect the HTML.")
    return False


async def human_scroll(page) -> None:
    """Simulate a human slowly scrolling down then back up."""
    try:
        for delta in [300, 400, 300, 200, -200, -300]:
            await page.mouse.wheel(0, delta)
            await page.wait_for_timeout(random.randint(120, 350))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Selector strategies
# ---------------------------------------------------------------------------

# Ordered list of CSS selectors to try when looking for listing cards.
# The first one that returns >= 1 elements wins.
CARD_SELECTORS = [
    # jawa.gg-specific: every listing title is an <a href="/product/...">
    "a[href*='/product/']",
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
    # Anchor-based fallbacks
    "a[href*='/listings/']",
    "a[href*='/item/']",
    # Grid children fallback — NOT ul/li which catches pagination
    "main article",
    "article",
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

    Handles two card shapes:
    - <a href="/product/..."> cards (jawa.gg's actual link structure): the
      element itself IS the title link; price lives in a sibling element.
    - Container cards (div/li/article wrapping an inner <a>): standard path.
    """
    scraped = now_iso()
    result: dict = {f: None for f in CSV_FIELDS}
    result["status"] = status
    result["date_scraped"] = scraped

    # Detect whether the matched element is itself the product <a> link
    is_anchor: bool = await card.evaluate("el => el.tagName === 'A'")

    # --- URL ---
    if is_anchor:
        href = await _attr(card, "href")
    else:
        # Prefer a direct /product/ link inside the card, then any <a>
        inner = card.locator("a[href*='/product/']")
        href = await _attr(inner.first, "href") if await inner.count() else ""
        if not href:
            href = await _attr(card.locator("a").first, "href")

    if href:
        full_url = href if href.startswith("http") else f"https://www.jawa.gg{href}"
        if "jawa.gg" in full_url:
            result["url"] = full_url

    # --- Title ---
    if is_anchor:
        # The link text IS the listing title (e.g. "RTX 4070 | Ryzen 5 7600X | 16GB | 1TB SSD")
        result["title"] = (await _text(card)) or None
    else:
        for sel in TITLE_SELECTORS:
            txt = await _text(card.locator(sel))
            # Reject suspiciously short strings (page numbers, icons, etc.)
            if txt and len(txt) > 8:
                result["title"] = txt
                break
        if not result["title"]:
            result["title"] = (await _text(card))[:200] or None

    # --- Price ---
    if is_anchor:
        # Price is NOT inside the <a> — walk next siblings via JS
        price_text: str = await card.evaluate("""el => {
            let node = el.nextElementSibling;
            for (let i = 0; i < 6 && node; i++, node = node.nextElementSibling) {
                const t = (node.textContent || '').trim();
                if (t.includes('$')) return t;
            }
            return '';
        }""")
        if price_text:
            m = re.search(r"\$\s*([\d,]+(?:\.\d{2})?)", price_text)
            if m:
                result["price"] = parse_price(m.group(1))
    else:
        for sel in PRICE_SELECTORS:
            txt = await _text(card.locator(sel))
            if txt and "$" in txt:
                result["price"] = parse_price(txt)
                break
        if result["price"] is None:
            full_text = await _text(card)
            m = re.search(r"\$\s*([\d,]+(?:\.\d{2})?)", full_text)
            if m:
                result["price"] = parse_price(m.group(1))

    # --- Dates ---
    # For <a> cards the date elements live outside the anchor; skip for now —
    # date_listed will be filled by deep_scrape_listing if needed.
    if not is_anchor:
        for sel in DATE_SELECTORS:
            loc = card.locator(sel)
            count = await loc.count()
            for i in range(count):
                item = loc.nth(i)
                txt = await _text(item)
                dt_attr = await _attr(item, "datetime")
                date_str = parse_date(dt_attr or txt)
                if date_str:
                    if status == "sold" and result["date_sold"] is None:
                        result["date_sold"] = date_str
                    elif result["date_listed"] is None:
                        result["date_listed"] = date_str

    # --- Specs (GPU, CPU, RAM, Storage) from title / full card text ---
    spec_source = result.get("title") or await _text(card)
    _fill_specs(result, spec_source)

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

        # Check for Cloudflare challenge and wait if needed
        if await is_cloudflare_challenge(page):
            cleared = await wait_for_cloudflare(page)
            if not cleared:
                print("  [CF] Could not bypass challenge — aborting section.")
                break
            await page.wait_for_timeout(int(random_delay(2.0, 3.0) * 1000))

        # Simulate human reading before scraping
        await human_scroll(page)

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

                # Deep-scrape if specs are missing OR if we need date_listed/date_sold
                needs_deep = (
                    listing.get("url")
                    and (
                        not any([listing.get("gpu"), listing.get("cpu"),
                                 listing.get("ram_gb"), listing.get("storage")])
                        or (status == "sold" and not listing.get("date_sold"))
                        or not listing.get("date_listed")
                    )
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

                # Skip non-product cards (newsletter signups, ads, etc.)
                title_text = (listing.get("title") or "").upper()
                if not listing.get("url") or any(
                    kw in title_text for kw in ("SIGN UP", "SUBSCRIBE", "NEWSLETTER", "EMAIL")
                ):
                    print(f"  [skip] Non-listing card: {title_text[:60]!r}")
                    continue

                page_listings.append(listing)

                total_so_far = len(listings) + len(page_listings)
                print(f"  Scraped listing {total_so_far}: "
                      f"{(listing.get('title') or 'untitled')[:60]}")

            except Exception as e:
                print(f"  [error] Skipping card {i+1}/{total_cards}: {e}")

        listings.extend(page_listings)

        # Persist cookies so next run skips the CF challenge
        try:
            save_cookies(await context.cookies())
        except Exception:
            pass

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
    if getattr(args, 'clear_cookies', False) and COOKIES_FILE.exists():
        COOKIES_FILE.unlink()
        print("[info] Cleared saved cookies — starting a fresh session.")

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
        await Stealth(
            navigator_webdriver=True, navigator_user_agent=True,
            navigator_languages=True, navigator_platform=True,
            navigator_plugins=True, navigator_vendor=True,
            navigator_permissions=True, navigator_hardware_concurrency=True,
            chrome_app=True, chrome_csi=True, chrome_load_times=True,
            chrome_runtime=False, webgl_vendor=True, media_codecs=True,
            hairline=True,
            navigator_platform_override="Win32",
            navigator_languages_override=("en-US", "en"),
        ).apply_stealth_async(context)

        # Restore saved cookies — skip the CF challenge on repeat runs
        saved_cookies = load_cookies()
        if saved_cookies:
            try:
                await context.add_cookies(saved_cookies)
                print(f"[info] Restored {len(saved_cookies)} saved cookies.")
            except Exception as e:
                print(f"[warn] Could not restore cookies: {e}")

        # Warm-up: visit homepage first so CF sees natural browsing behaviour
        print("\n[warm-up] Visiting jawa.gg homepage…")
        warmup = await context.new_page()
        try:
            await warmup.goto("https://www.jawa.gg", wait_until="domcontentloaded", timeout=30_000)
            await warmup.wait_for_timeout(int(random_delay(2.5, 4.0) * 1000))
            if await is_cloudflare_challenge(warmup):
                await wait_for_cloudflare(warmup)
            await human_scroll(warmup)
            save_cookies(await context.cookies())
            print("[warm-up] Done.")
        except Exception as e:
            print(f"[warm-up] Skipped: {e}")
        finally:
            await warmup.close()
        await asyncio.sleep(random_delay(2.0, 3.0))

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

        # Final cookie save
        try:
            save_cookies(await context.cookies())
        except Exception:
            pass
        await browser.close()

    # Deduplicate by URL (keep first occurrence)
    seen_urls: set[str] = set()
    unique_listings: list[dict] = []
    for lst in all_listings:
        url = lst.get("url") or ""
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        unique_listings.append(lst)

    removed = len(all_listings) - len(unique_listings)
    if removed:
        print(f"Removed {removed} duplicate listing(s).")

    print(f"\nTotal listings: {len(unique_listings)}")
    if unique_listings:
        save_csv(unique_listings, OUTPUT_CSV)
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
    parser.add_argument("--clear-cookies", action="store_true",
                        help="Delete saved session cookies and start a fresh CF session")
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
