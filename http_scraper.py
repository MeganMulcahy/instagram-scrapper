"""
Layer 1: Raw HTTP scraper.
Hits the public Instagram URL with realistic headers,
extracts the embedded JSON blob Instagram bakes into every page.
No browser needed — fast and cheap.
Falls back to None if Instagram returns a login wall or empty data.
"""

import re
import json
import random
import asyncio
import httpx
from bs4 import BeautifulSoup

from app.core.config import MOBILE_HEADERS, PROXY_URL, INSTAGRAM_SESSION_ID
from app.models.schemas import ReelData


# Pool of realistic user agents to rotate
USER_AGENTS = [
    (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.4 Mobile/15E148 Safari/604.1"
    ),
    (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/16.6 Mobile/15E148 Safari/604.1"
    ),
    (
        "Mozilla/5.0 (Linux; Android 14; Pixel 8) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Mobile Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Linux; Android 13; Samsung Galaxy S23) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Mobile Safari/537.36"
    ),
]


def _build_headers() -> dict:
    headers = MOBILE_HEADERS.copy()
    headers["User-Agent"] = random.choice(USER_AGENTS)
    if INSTAGRAM_SESSION_ID:
        headers["Cookie"] = f"sessionid={INSTAGRAM_SESSION_ID}"
    return headers


def _extract_shortcode(url: str) -> str:
    match = re.search(r"/reel/([A-Za-z0-9_-]+)", url)
    return match.group(1) if match else ""


def _parse_json_blob(html: str) -> dict | None:
    """
    Instagram embeds structured data in multiple places in the page HTML.
    We try each known pattern in order of reliability.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Pattern 1: <script type="application/json" data-content-len> (newer)
    for tag in soup.find_all("script", {"type": "application/json"}):
        try:
            data = json.loads(tag.string or "")
            # Look for the media object
            if _find_media(data):
                return _find_media(data)
        except (json.JSONDecodeError, TypeError):
            continue

    # Pattern 2: window.__additionalDataLoaded (older, still common)
    match = re.search(
        r'window\.__additionalDataLoaded\s*\(\s*[\'"][^\'"]*[\'"]\s*,\s*(\{.*?\})\s*\)',
        html, re.DOTALL
    )
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Pattern 3: __NEXT_DATA__ / __RELAY_STORE__
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(\{.*?\})</script>', html, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    return None


def _find_media(obj, depth=0) -> dict | None:
    """Recursively find a media object that looks like a Reel."""
    if depth > 10 or not isinstance(obj, (dict, list)):
        return None
    if isinstance(obj, list):
        for item in obj:
            result = _find_media(item, depth + 1)
            if result:
                return result
    if isinstance(obj, dict):
        # A reel media object has these keys
        if "video_url" in obj and "shortcode" in obj:
            return obj
        for v in obj.values():
            result = _find_media(v, depth + 1)
            if result:
                return result
    return None


def _parse_media(media: dict, url: str) -> ReelData:
    """Map raw Instagram media JSON to our clean ReelData schema."""
    caption_obj = media.get("edge_media_to_caption", {}).get("edges", [])
    caption     = caption_obj[0]["node"]["text"] if caption_obj else ""
    hashtags    = re.findall(r"#(\w+)", caption)

    owner    = media.get("owner", {})
    username = owner.get("username", "") or owner.get("full_name", "")

    audio = media.get("clips_music_attribution_info", {})

    return ReelData(
        url           = url,
        shortcode     = media.get("shortcode", _extract_shortcode(url)),
        username      = username,
        caption       = caption,
        hashtags      = hashtags,
        video_url     = media.get("video_url"),
        thumbnail_url = media.get("display_url"),
        duration      = media.get("video_duration"),
        views         = media.get("video_view_count"),
        likes         = media.get("edge_media_preview_like", {}).get("count"),
        audio_name    = audio.get("song_name") or audio.get("artist_name"),
        scraped_via   = "http",
    )


async def scrape_http(url: str) -> ReelData | None:
    """
    Attempt to scrape a Reel via raw HTTP.
    Returns ReelData on success, None if we need to fall back to Playwright.
    """
    # Small random delay — humans don't make instant requests
    await asyncio.sleep(random.uniform(0.8, 2.5))

    proxies = {"http://": PROXY_URL, "https://": PROXY_URL} if PROXY_URL else None

    async with httpx.AsyncClient(
        headers=_build_headers(),
        follow_redirects=True,
        timeout=20,
        proxies=proxies,
        http2=True,
    ) as client:
        try:
            resp = await client.get(url)
        except httpx.RequestError:
            return None

    if resp.status_code != 200:
        return None

    # Instagram returns a login redirect for restricted content
    if "login" in str(resp.url) or "accounts/login" in resp.text:
        return None

    media = _parse_json_blob(resp.text)
    if not media:
        return None

    return _parse_media(media, url)
