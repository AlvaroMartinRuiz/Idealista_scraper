"""
scraper.py — Single-session Playwright scraper with robust CAPTCHA handling.
"""
import asyncio
import random
import logging
import sys
import threading
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Page, Locator
from playwright_stealth.stealth import Stealth

from utils import FAKE_USER_AGENT, build_search_url

logger = logging.getLogger(__name__)
STORAGE_DIR = Path(__file__).parent / ".browser_state"
STORAGE_FILE = STORAGE_DIR / "state.json"


async def _human_jitter(page: Page, seconds_range=(3, 7)) -> None:
    lo, hi = seconds_range
    await page.wait_for_timeout(random.uniform(lo * 1000, hi * 1000))
    try:
        await page.evaluate(f"window.scrollBy(0, {random.randint(100, 400)})")
        await page.wait_for_timeout(random.uniform(500, 1500))
        vw = await page.evaluate("window.innerWidth")
        vh = await page.evaluate("window.innerHeight")
        await page.mouse.move(random.uniform(50, vw - 50), random.uniform(50, vh - 50))
    except Exception:
        pass
    await page.wait_for_timeout(random.uniform(300, 800))


async def _is_captcha(page: Page) -> bool:
    try:
        # Check for Datadome iframe specifically
        iframe_count = await page.locator("iframe[src*='datadome'], iframe[src*='geo.captcha']").count()
        if iframe_count > 0:
            return True
            
        content = (await page.content()).lower()
        return any(kw in content for kw in ["datadome", "geo.captcha", "desliza hacia la derecha", "un robot se encuentra"])
    except Exception as e:
        logger.warning(f"Error checking captcha status: {e}")
        # If we get an exception (e.g. context destroyed during navigation), assume True to avoid premature skip
        return True


async def _handle_captcha(page: Page, headless: bool, status_cb=None) -> bool:
    """If CAPTCHA is present, wait for user to solve it. Returns True if page is clean."""
    if not await _is_captcha(page):
        return True  # No captcha, we're good

    if headless:
        logger.error("CAPTCHA detected in headless mode — cannot solve.")
        if status_cb:
            status_cb("CAPTCHA detected but running headless — cannot solve. Disable headless mode.")
        return False

    msg = "⚠️ CAPTCHA detected! Solve the slider in the Chromium window. Waiting up to 3 minutes..."
    logger.warning(msg)
    if status_cb:
        status_cb(msg)

    # Poll until CAPTCHA is gone (user solved it) or timeout
    consecutive_clean = 0
    for _ in range(90):  # 90 * 2s = 180s
        await page.wait_for_timeout(2000)
        
        is_cap = await _is_captcha(page)
        
        if not is_cap:
            consecutive_clean += 1
            if consecutive_clean >= 3:
                logger.info("CAPTCHA solved!")
                if status_cb:
                    status_cb("CAPTCHA solved! Continuing in a few seconds...")
                # Give the page time to fully load after Datadome redirect
                await page.wait_for_timeout(random.uniform(4000, 7000))
                return True
        else:
            consecutive_clean = 0

    logger.error("CAPTCHA timeout — 3 minutes elapsed.")
    if status_cb:
        status_cb("CAPTCHA timeout.")
    return False


async def _extract_card(article, zone_name: str) -> dict:
    result = {
        "zone": zone_name, "link": None, "price_raw": None,
        "m2_raw": None, "rooms_raw": None, "restrooms_raw": "N/A", "location_raw": None,
    }
    try:
        href = await article.locator("a.item-link").first.get_attribute("href")
        if href:
            result["link"] = f"https://www.idealista.com{href}" if href.startswith("/") else href
    except Exception:
        pass

    try:
        price_el = article.locator("span.item-price").first
        if await price_el.count() > 0:
            result["price_raw"] = (await price_el.inner_text()).strip()
    except Exception:
        pass

    try:
        features = article.locator("span.item-detail")
        for i in range(await features.count()):
            text = (await features.nth(i).inner_text()).strip()
            tl = text.lower()
            if "m²" in tl or "m2" in tl:
                result["m2_raw"] = text
            elif "hab" in tl:
                result["rooms_raw"] = text
            elif "baño" in tl or "aseo" in tl:
                result["restrooms_raw"] = text
    except Exception:
        pass

    try:
        loc = article.locator("span[class*='item-detail-location'], .item-address span").first
        if await loc.count() > 0:
            result["location_raw"] = (await loc.inner_text()).strip()
    except Exception:
        pass

    return result


async def _scrape_all(zone_names, max_price, min_rooms, max_per_zone,
                      headless, progress_cb, status_cb):
    all_listings = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled", "--no-first-run"],
        )
        ctx_kw = {"user_agent": FAKE_USER_AGENT, "viewport": {"width": 1366, "height": 768}, "locale": "es-ES"}
        if STORAGE_FILE.exists():
            ctx_kw["storage_state"] = str(STORAGE_FILE)

        context = await browser.new_context(**ctx_kw)
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)

        # --- Warm-up: visit homepage ---
        try:
            if status_cb:
                status_cb("Visiting Idealista homepage to establish session...")
            await page.goto("https://www.idealista.com/", wait_until="domcontentloaded", timeout=45000)
            await _human_jitter(page, (3, 6))

            # Accept cookies
            try:
                btn = page.locator("button#didomi-notice-agree-button")
                if await btn.is_visible(timeout=4000):
                    await btn.click()
                    await page.wait_for_timeout(random.uniform(1000, 2000))
            except Exception:
                pass

            # Handle CAPTCHA on homepage
            captcha_ok = await _handle_captcha(page, headless, status_cb)
            if not captcha_ok:
                await browser.close()
                return all_listings

            # Save session after warm-up
            STORAGE_DIR.mkdir(exist_ok=True)
            await context.storage_state(path=str(STORAGE_FILE))
            await _human_jitter(page, (5, 10))

        except Exception as e:
            logger.exception("Warm-up failed:")
            # Continue anyway — maybe the zone pages will work

        # --- Scrape each zone ---
        for zi, zone in enumerate(zone_names):
            logger.info(f"Zone {zi+1}/{len(zone_names)}: {zone}")
            if status_cb:
                status_cb(f"Scraping zone {zi+1}/{len(zone_names)}: {zone}")

            zone_listings = []
            page_num = 1
            empty_pages = 0

            while len(zone_listings) < max_per_zone and empty_pages < 2:
                url = build_search_url(zone, max_price, min_rooms, page=page_num)
                logger.info(f"  [{zone}] page {page_num}: {url}")

                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                except Exception as e:
                    logger.warning(f"  [{zone}] Navigation error: {e}")
                    break

                await _human_jitter(page, (3, 7))

                # Handle CAPTCHA
                captcha_ok = await _handle_captcha(page, headless, status_cb)
                if not captcha_ok:
                    logger.warning(f"  [{zone}] CAPTCHA not solved, skipping zone.")
                    break

                # Extract listings
                articles = page.locator("article.item")
                count = await articles.count()
                logger.info(f"  [{zone}] Found {count} articles on page {page_num}")

                if count == 0:
                    empty_pages += 1
                    page_num += 1
                    continue

                empty_pages = 0
                for i in range(count):
                    card = await _extract_card(articles.nth(i), zone)
                    if card["price_raw"] and card["m2_raw"]:
                        zone_listings.append(card)
                    if len(zone_listings) >= max_per_zone:
                        break

                if progress_cb:
                    progress_cb(zone, page_num, len(all_listings) + len(zone_listings))

                page_num += 1
                await _human_jitter(page, (6, 12))  # Long delay between pages

            all_listings.extend(zone_listings)
            logger.info(f"  [{zone}] Collected {len(zone_listings)} listings.")

            # Save cookies after each zone
            try:
                await context.storage_state(path=str(STORAGE_FILE))
            except Exception:
                pass

            # Long delay between zones (10-20s)
            if zi < len(zone_names) - 1:
                wait = random.uniform(10, 20)
                logger.info(f"  Waiting {wait:.0f}s before next zone...")
                if status_cb:
                    status_cb(f"Waiting {wait:.0f}s before next zone...")
                await page.wait_for_timeout(wait * 1000)

        await browser.close()

    return all_listings


def run_all_zones(zone_names, max_price, min_rooms, max_listings=15,
                  headless=True, progress_callback=None, status_callback=None):
    """Sync entry point. Runs scraper in a dedicated thread (Windows compat)."""
    from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
    
    result = []

    def _run():
        nonlocal result
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                _scrape_all(zone_names, max_price, min_rooms, max_listings,
                            headless, progress_callback, status_callback)
            )
        except Exception as e:
            if "TargetClosedError" in str(e) or "has been closed" in str(e):
                logger.error("Browser was closed manually. Scraper stopped.")
            else:
                logger.exception("Scraper thread failed:")
        finally:
            loop.close()

    t = threading.Thread(target=_run)
    
    # Attach Streamlit context so callbacks can update the UI from this thread
    ctx = get_script_run_ctx()
    if ctx:
        add_script_run_ctx(t, ctx)
        
    t.start()
    t.join()
    return result
