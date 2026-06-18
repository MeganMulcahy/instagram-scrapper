"""
Layer 4: yt-dlp fallback.
"""

import asyncio
import re

import yt_dlp

from app.models.schemas import ReelData
from app.scrapers.identity_pool import ScrapeIdentity
from app.scrapers.parsers import extract_shortcode


async def scrape_ytdlp(url: str, identity: ScrapeIdentity) -> ReelData | None:
    return await asyncio.to_thread(_scrape_sync, url, identity)


def _scrape_sync(url: str, identity: ScrapeIdentity) -> ReelData | None:
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }

    if identity.session_id:
        ydl_opts["http_headers"] = {
            "Cookie": f"sessionid={identity.session_id}",
        }

    if identity.proxy_url:
        ydl_opts["proxy"] = identity.proxy_url

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        return None

    if not info:
        return None

    description = info.get("description", "") or info.get("title", "")
    hashtags = re.findall(r"#(\w+)", description)
    username = (info.get("uploader_id") or "").lstrip("@") or info.get("uploader", "")

    return ReelData(
        url=url,
        shortcode=extract_shortcode(url),
        username=username,
        caption=description,
        hashtags=hashtags,
        video_url=info.get("url"),
        thumbnail_url=info.get("thumbnail"),
        duration=info.get("duration"),
        views=info.get("view_count"),
        likes=info.get("like_count"),
        audio_name=info.get("track") or info.get("artist"),
        scraped_via="ytdlp",
    )
