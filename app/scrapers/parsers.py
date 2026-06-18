"""
JSON blob extraction and media parsing.
Targets embedded data in page source — never div IDs or class names.
"""

import json
import re

from bs4 import BeautifulSoup

from app.models.schemas import ReelData, ScrapedVia


def normalize_instagram_url(url: str) -> str:
    """Normalize Instagram URLs — /reels/ → /reel/, strip query params."""
    url = url.strip()
    url = re.sub(r"(https?://(?:www\.)?instagram\.com)/reels/", r"\1/reel/", url, flags=re.I)
    url = url.split("?")[0].rstrip("/") + "/"
    return url


def extract_shortcode(url: str) -> str:
    match = re.search(r"/(?:reels?|p|tv)/([A-Za-z0-9_-]+)", url, re.I)
    return match.group(1) if match else ""


def shortcode_to_media_id(shortcode: str) -> str:
    """Convert Instagram shortcode to numeric media ID."""
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    media_id = 0
    for char in shortcode:
        media_id = media_id * 64 + alphabet.index(char)
    return str(media_id)


def _looks_like_media(obj: dict) -> bool:
    has_id = bool(obj.get("shortcode") or obj.get("code"))
    has_video = bool(obj.get("video_url") or obj.get("video_versions"))
    return has_id and has_video


def _media_score(obj: dict) -> int:
    """Prefer the most complete media object when multiple are found."""
    score = 0
    if obj.get("video_url") or obj.get("video_versions"):
        score += 10
    owner = obj.get("owner") or obj.get("user") or {}
    if owner.get("username"):
        score += 5
    caption = obj.get("caption")
    if isinstance(caption, dict) and caption.get("text"):
        score += 3
    elif obj.get("edge_media_to_caption", {}).get("edges"):
        score += 3
    if obj.get("display_url") or obj.get("image_versions2"):
        score += 2
    if obj.get("like_count") or obj.get("edge_media_preview_like"):
        score += 1
    return score


def _collect_media(obj, candidates: list[dict], depth: int = 0) -> None:
    if depth > 12 or not isinstance(obj, (dict, list)):
        return
    if isinstance(obj, list):
        for item in obj:
            _collect_media(item, candidates, depth + 1)
    elif isinstance(obj, dict):
        if _looks_like_media(obj):
            candidates.append(obj)
        # GraphQL wrapper — check known keys before deep recursion
        data = obj.get("data")
        if isinstance(data, dict):
            for key in ("xdt_shortcode_media", "shortcode_media", "media"):
                if isinstance(data.get(key), dict) and _looks_like_media(data[key]):
                    candidates.append(data[key])
        for value in obj.values():
            _collect_media(value, candidates, depth + 1)


def find_media(obj, depth: int = 0) -> dict | None:
    """Find the best media object in a nested JSON payload."""
    candidates: list[dict] = []
    _collect_media(obj, candidates, depth)
    if not candidates:
        return None
    return max(candidates, key=_media_score)


def parse_json_blob(html: str) -> dict | None:
    """
    Extract embedded JSON from Instagram page HTML.
    Tries every known blob pattern — same strategy Apify uses.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Pattern 1: <script type="application/json"> (current primary)
    for tag in soup.find_all("script", {"type": "application/json"}):
        try:
            data = json.loads(tag.string or "")
            if media := find_media(data):
                return media
        except (json.JSONDecodeError, TypeError):
            continue

    # Pattern 2: window.__additionalDataLoaded
    match = re.search(
        r"window\.__additionalDataLoaded\s*\(\s*['\"][^'\"]*['\"]\s*,\s*(\{.*?\})\s*\)\s*;",
        html,
        re.DOTALL,
    )
    if match:
        try:
            data = json.loads(match.group(1))
            if media := find_media(data):
                return media
        except json.JSONDecodeError:
            pass

    # Pattern 3: window._sharedData (legacy, still seen)
    match = re.search(r"window\._sharedData\s*=\s*(\{.*?\});</script>", html, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            if media := find_media(data):
                return media
        except json.JSONDecodeError:
            pass

    # Pattern 4: __NEXT_DATA__
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(\{.*?\})</script>', html, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            if media := find_media(data):
                return media
        except json.JSONDecodeError:
            pass

    return None


def is_usable_result(data: ReelData) -> bool:
    """Reject partial scrapes that only have a likes count."""
    if not data.shortcode:
        return False
    return bool(data.video_url or data.username or data.caption)


def parse_web_media(media: dict, url: str, scraped_via: ScrapedVia = "http") -> ReelData:
    """Map web-embedded JSON (GraphQL shape) to ReelData."""
    caption_obj = media.get("edge_media_to_caption", {}).get("edges", [])
    caption = caption_obj[0]["node"]["text"] if caption_obj else ""
    if not caption and isinstance(media.get("caption"), dict):
        caption = media["caption"].get("text", "")

    hashtags = re.findall(r"#(\w+)", caption)

    owner = media.get("owner") or media.get("user") or {}
    username = owner.get("username", "") or owner.get("full_name", "")
    audio = media.get("clips_music_attribution_info") or {}
    if not audio:
        music = (media.get("clips_metadata") or {}).get("music_info", {}).get("music_asset_info", {})
        audio = {"song_name": music.get("title"), "artist_name": music.get("display_artist")}

    video_url = media.get("video_url")
    if not video_url:
        versions = media.get("video_versions") or []
        video_url = versions[0]["url"] if versions else None

    thumbnail = media.get("display_url") or media.get("thumbnail_src")
    if not thumbnail:
        candidates = (media.get("image_versions2") or {}).get("candidates") or []
        thumbnail = candidates[0]["url"] if candidates else None

    return ReelData(
        url=url,
        shortcode=media.get("shortcode") or media.get("code") or extract_shortcode(url),
        username=username,
        caption=caption,
        hashtags=hashtags,
        video_url=video_url,
        thumbnail_url=thumbnail,
        duration=media.get("video_duration"),
        views=media.get("video_view_count") or media.get("play_count") or media.get("view_count"),
        likes=media.get("edge_media_preview_like", {}).get("count") or media.get("like_count"),
        audio_name=audio.get("song_name") or audio.get("artist_name"),
        scraped_via=scraped_via,
    )


def _dig(obj: dict | None, *keys, default=None):
    """Safely traverse nested dicts — handles None at any level."""
    current = obj
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return current if current is not None else default


def parse_mobile_api_item(item: dict, url: str) -> ReelData:
    """Map Instagram mobile API response item to ReelData."""
    caption_obj = item.get("caption") or {}
    caption = caption_obj.get("text", "") if isinstance(caption_obj, dict) else str(caption_obj or "")
    hashtags = re.findall(r"#(\w+)", caption)

    user = item.get("user") or {}
    username = user.get("username", "") or user.get("full_name", "")

    video_versions = item.get("video_versions") or []
    video_url = video_versions[0]["url"] if video_versions else None

    thumb_candidates = _dig(item, "image_versions2", "candidates", default=[]) or []
    thumbnail_url = thumb_candidates[0]["url"] if thumb_candidates else None

    music = _dig(item, "clips_metadata", "music_info", "music_asset_info", default={}) or {}

    return ReelData(
        url=url,
        shortcode=item.get("code") or extract_shortcode(url),
        username=username,
        caption=caption,
        hashtags=hashtags,
        video_url=video_url,
        thumbnail_url=thumbnail_url,
        duration=item.get("video_duration"),
        views=item.get("play_count") or item.get("view_count"),
        likes=item.get("like_count"),
        audio_name=music.get("title") or music.get("display_artist"),
        scraped_via="mobile_api",
    )
