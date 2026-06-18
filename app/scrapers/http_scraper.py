"""
Layer 1: Raw HTTP scraper.
Hits the public Instagram URL with realistic headers,
extracts the embedded JSON blob Instagram bakes into every page.
"""

import httpx

from app.models.schemas import ReelData
from app.scrapers.headers import build_web_headers
from app.scrapers.identity_pool import ScrapeIdentity
from app.scrapers.parsers import parse_json_blob, parse_web_media


async def scrape_http(url: str, identity: ScrapeIdentity) -> ReelData | None:
    async with httpx.AsyncClient(
        headers=build_web_headers(identity),
        follow_redirects=True,
        timeout=20,
        proxy=identity.proxy_url,
        http2=True,
    ) as client:
        try:
            resp = await client.get(url)
        except httpx.RequestError:
            return None

    if resp.status_code != 200:
        return None

    if "login" in str(resp.url) or "accounts/login" in resp.text:
        return None

    media = parse_json_blob(resp.text)
    if not media:
        return None

    return parse_web_media(media, url, scraped_via="http")
