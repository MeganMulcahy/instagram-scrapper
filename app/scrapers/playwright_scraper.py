"""
Layer 3: Playwright headless browser fallback.
Renders the page like a real mobile browser, then parses embedded JSON.
"""

import asyncio
import random

from playwright.async_api import TimeoutError as PWTimeout
from playwright.async_api import async_playwright

from app.models.schemas import ReelData
from app.scrapers.identity_pool import ScrapeIdentity
from app.scrapers.parsers import find_media, parse_json_blob, parse_web_media


async def scrape_playwright(url: str, identity: ScrapeIdentity) -> ReelData | None:
    async with async_playwright() as p:
        launch_opts = {
            "headless": True,
            "args": [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        }
        if identity.proxy_url:
            launch_opts["proxy"] = {"server": identity.proxy_url}

        browser = await p.chromium.launch(**launch_opts)

        context = await browser.new_context(
            **p.devices["iPhone 14 Pro"],
            locale="en-US",
            timezone_id="America/Chicago",
        )

        if identity.session_id:
            await context.add_cookies([{
                "name": "sessionid",
                "value": identity.session_id,
                "domain": ".instagram.com",
                "path": "/",
                "secure": True,
                "httpOnly": True,
            }])

        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
        """)

        page = await context.new_page()
        captured_media: list[dict] = []

        async def handle_response(response):
            if any(k in response.url for k in ("graphql", "api/v1/media", "api/v1/clips")):
                try:
                    captured_media.append(await response.json())
                except Exception:
                    pass

        page.on("response", handle_response)

        try:
            await page.goto(url, wait_until="networkidle", timeout=30_000)
            await asyncio.sleep(random.uniform(1.5, 3.0))
        except PWTimeout:
            await browser.close()
            return None

        for payload in captured_media:
            if media := find_media(payload):
                await browser.close()
                return parse_web_media(media, url, scraped_via="playwright")

        html = await page.content()
        await browser.close()

        if media := parse_json_blob(html):
            return parse_web_media(media, url, scraped_via="playwright")

    return None
