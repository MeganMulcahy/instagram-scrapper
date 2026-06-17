"""
Layer 3: yt-dlp fallback.
If both HTTP and Playwright fail to get structured JSON,
yt-dlp can still pull the video URL and basic metadata.
It's the most reliable for actually getting the video file.
"""

import re
import asyncio
import yt_dlp

from app.core.config import INSTAGRAM_SESSION_ID
from app.models.schemas import ReelData


def _extract_shortcode(url: str) -> str:
    match = re.search(r"/reel/([A-Za-z0-9_-]+)", url)
    return match.group(1) if match else ""


async def scrape_ytdlp(url: str) -> ReelData | None:
    return await asyncio.to_thread(_scrape_sync, url)


def _scrape_sync(url: str) -> ReelData | None:
    ydl_opts = {
        "quiet":       True,
        "no_warnings": True,
        "skip_download": True,       # metadata only — no actual download
    }

    if INSTAGRAM_SESSION_ID:
        ydl_opts["http_headers"] = {
            "Cookie": f"sessionid={INSTAGRAM_SESSION_ID}",
        }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        return None

    if not info:
        return None

    description = info.get("description", "") or info.get("title", "")
    hashtags    = re.findall(r"#(\w+)", description)
    username    = (info.get("uploader_id") or "").lstrip("@") or info.get("uploader", "")

    return ReelData(
        url           = url,
        shortcode     = _extract_shortcode(url),
        username      = username,
        caption       = description,
        hashtags      = hashtags,
        video_url     = info.get("url"),
        thumbnail_url = info.get("thumbnail"),
        duration      = info.get("duration"),
        views         = info.get("view_count"),
        likes         = info.get("like_count"),
        audio_name    = info.get("track") or info.get("artist"),
        scraped_via   = "ytdlp",
    )
