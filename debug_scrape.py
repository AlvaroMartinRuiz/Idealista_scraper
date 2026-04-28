"""
debug_scrape.py - Minimal diagnostic script for Idealista scraping.
Run with: python debug_scrape.py
"""
import asyncio
import random
from playwright.async_api import async_playwright
from playwright_stealth.stealth import Stealth
from utils import FAKE_USER_AGENT, build_search_url

TEST_ZONE = "madrid/latina/aluche"

async def diagnose():
    url = build_search_url(TEST_ZONE, 2400, 3)
    print(f"\nTARGET URL: {url}\n")

    async with async_playwright() as p:
        # Launch VISIBLE browser with extra anti-detection args
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-dev-shm-usage",
            ],
        )
        context = await browser.new_context(
            user_agent=FAKE_USER_AGENT,
            viewport={"width": 1366, "height": 768},
            locale="es-ES",
            java_script_enabled=True,
        )
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)

        # Remove webdriver flag explicitly
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['es-ES', 'es', 'en'] });
            window.chrome = { runtime: {} };
        """)

        # Step 1: First navigate to idealista homepage to get cookies
        print("[1] Loading idealista.com homepage first...")
        try:
            resp = await page.goto("https://www.idealista.com/", wait_until="domcontentloaded", timeout=30_000)
            print(f"    Homepage HTTP status: {resp.status if resp else 'None'}")
        except Exception as e:
            print(f"    Homepage error: {e}")

        await page.wait_for_timeout(random.uniform(3000, 5000))

        # Accept cookies
        print("[2] Checking for cookie banner...")
        try:
            btn = page.locator("button#didomi-notice-agree-button")
            if await btn.is_visible(timeout=4000):
                await btn.click()
                print("    -> Dismissed cookie banner.")
                await page.wait_for_timeout(1500)
            else:
                print("    -> No cookie banner.")
        except Exception:
            print("    -> No cookie banner found.")

        # Scroll a bit on homepage
        await page.evaluate("window.scrollBy(0, 300)")
        await page.wait_for_timeout(random.uniform(2000, 4000))

        # Step 2: Now navigate to the actual search URL
        print(f"[3] Navigating to search URL...")
        try:
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            print(f"    HTTP status: {resp.status if resp else 'None'}")
            print(f"    Final URL:   {page.url}")
        except Exception as e:
            print(f"    NAVIGATION ERROR: {e}")
            await browser.close()
            return

        await page.wait_for_timeout(random.uniform(3000, 5000))

        # Human-like scroll
        await page.evaluate("window.scrollBy(0, window.innerHeight * 0.5)")
        await page.wait_for_timeout(random.uniform(1000, 2000))

        # Check page title
        title = await page.title()
        print(f"[4] Page title: {title}")

        # Check for block indicators
        content = await page.content()
        content_lower = content.lower()
        
        block_keywords = ["captcha", "datadome", "blocked", "access denied", "no autorizado",
                         "too many requests", "rate limit", "challenge-platform", "geo.captcha"]
        found_blocks = [kw for kw in block_keywords if kw in content_lower]
        if found_blocks:
            print(f"[5] BLOCK INDICATORS FOUND: {found_blocks}")
        else:
            print("[5] No block indicators detected.")

        # Check for listing articles with multiple selector strategies
        selectors_to_try = [
            "article.item",
            "article.item-multimedia-container",
            ".item-info-container",
            "article[data-adid]",
            ".items-list article",
            "section.items-list article",
            "div.listing-items article",
        ]
        
        print("[6] Searching for listing elements:")
        for sel in selectors_to_try:
            c = await page.locator(sel).count()
            if c > 0:
                print(f"    -> '{sel}': {c} elements FOUND")
            
        articles = page.locator("article.item")
        article_count = await articles.count()

        if article_count == 0:
            body_text = await page.locator("body").inner_text()
            print(f"\n[7] Body text (first 2000 chars):")
            print("-" * 40)
            # Encode safely for Windows console
            safe_text = body_text[:2000].encode("ascii", errors="replace").decode()
            print(safe_text)
            print("-" * 40)
        else:
            print(f"    Found {article_count} listings!")
            first = articles.nth(0)
            try:
                price = await first.locator("span.item-price").first.inner_text()
                print(f"    Sample price: {price}")
            except:
                print("    Could not extract sample price.")

        # Save screenshot
        await page.screenshot(path="debug_screenshot.png", full_page=True)
        print(f"\n[8] Screenshot saved to: debug_screenshot.png")
        
        print("\n[9] Keeping browser open for 20s so you can inspect...")
        await page.wait_for_timeout(20000)

        await browser.close()

    print("\nDone!")

if __name__ == "__main__":
    asyncio.run(diagnose())
