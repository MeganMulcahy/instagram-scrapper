"""
Layer 2: Playwright headless browser fallback.
Used when the raw HTTP layer gets a login wall or empty JSON.
Renders the page like a real mobile browser — much harder for
Instagram to distinguish from a real user.
"""

import re
import json
import asyncio
import random

from playwright.async_api import async_playwright, TimeoutError as PWTimeout
from app.core.config import PROXY_URL, INSTAGRAM_SESSION_ID
from app.models.schemas import ReelData
from app.scrapers.http_scraper import _parse_json_blob, _parse_media, _extract_shortcode


async def scrape_playwright(url: str) -> ReelData | None:
    """
    Launch a headless mobile Chrome browser, navigate to the Reel,
    intercept the page JSON, and extract the media object.
    """
    async with async_playwright() as p:
        launch_opts = {
            "headless": True,
            "args": [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        }
        if PROXY_URL:
            launch_opts["proxy"] = {"server": PROXY_URL}

        browser = await p.chromium.launch(**launch_opts)

        # Emulate iPhone 14 Pro
        context = await browser.new_context(
            **p.devices["iPhone 14 Pro"],
            locale="en-US",
            timezone_id="America/Chicago",
        )

        # Inject session cookie if available
        if INSTAGRAM_SESSION_ID:
            await context.add_cookies([{
                "name":   "sessionid",
                "value":  INSTAGRAM_SESSION_ID,
                "domain": ".instagram.com",
                "path":   "/",
                "secure": True,
                "httpOnly": True,
            }])

        # Hide automation fingerprints
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
        """)

        page = await context.new_page()

        # Intercept API responses that contain media data
        captured_media: list[dict] = []

        async def handle_response(response):
            if "graphql" in response.url or "api/v1/media" in response.url:
                try:
                    body = await response.json()
                    captured_media.append(body)
                except Exception:
                    pass

        page.on("response", handle_response)

        try:
            await page.goto(url, wait_until="networkidle", timeout=30_000)
            await asyncio.sleep(random.uniform(1.5, 3.0))  # human pause
        except PWTimeout:
            await browser.close()
            return None

        # First try intercepted API responses
        for payload in captured_media:
            media = _find_media_in_payload(payload)
            if media:
                await browser.close()
                return _parse_media(media, url)

        # Fall back to parsing the rendered HTML
        html = await page.content()
        await browser.close()

        media = _parse_json_blob(html)
        if media:
            return _parse_media(media, url)

    return None


def _find_media_in_payload(obj, depth=0) -> dict | None:
    if depth > 8 or not isinstance(obj, (dict, list)):
        return None
    if isinstance(obj, list):
        for item in obj:
            r = _find_media_in_payload(item, depth + 1)
            if r:
                return r
    if isinstance(obj, dict):
        if "video_url" in obj and "shortcode" in obj:
            return obj
        for v in obj.values():
            r = _find_media_in_payload(v, depth + 1)
            if r:
                return r
    return None
