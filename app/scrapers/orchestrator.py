"""
Scraper orchestrator — Apify-style layered fallback with identity rotation.
"""

import logging

from app.core.config import MAX_RETRIES
from app.models.schemas import ReelData
from app.scrapers.http_scraper import scrape_http
from app.scrapers.identity_pool import ScrapeIdentity, identity_pool
from app.scrapers.mobile_api_scraper import scrape_mobile_api
from app.scrapers.parsers import is_usable_result, normalize_instagram_url
from app.scrapers.playwright_scraper import scrape_playwright
from app.scrapers.ytdlp_scraper import scrape_ytdlp

logger = logging.getLogger(__name__)


async def scrape_reel(
    url: str,
    include_transcript: bool = False,
    include_ocr: bool = False,
) -> ReelData | None:
    url = normalize_instagram_url(url)

    for attempt in range(1, MAX_RETRIES + 1):
        identity = await identity_pool.acquire()
        logger.info(f"Attempt {attempt}/{MAX_RETRIES} using {identity.label}")

        result = await _scrape_with_identity(url, identity)
        if result and is_usable_result(result):
            return await _finalize(result, include_transcript, include_ocr)

        logger.warning(f"Attempt {attempt} failed — rotating identity")

    logger.warning(f"All {MAX_RETRIES} attempts failed for {url}")
    return None


async def _scrape_with_identity(url: str, identity: ScrapeIdentity) -> ReelData | None:
    logger.info(f"[HTTP] Trying {url}")
    if result := await scrape_http(url, identity):
        if is_usable_result(result):
            logger.info(f"[HTTP] Success — @{result.username}")
            return result
        logger.info("[HTTP] Partial data only, trying next layer")

    logger.info("[Mobile API] Trying mobile API")
    if result := await scrape_mobile_api(url, identity):
        if is_usable_result(result):
            logger.info(f"[Mobile API] Success — @{result.username}")
            return result
        logger.info("[Mobile API] Partial data only, trying next layer")

    logger.info("[Playwright] Trying browser")
    if result := await scrape_playwright(url, identity):
        if is_usable_result(result):
            logger.info(f"[Playwright] Success — @{result.username}")
            return result
        logger.info("[Playwright] Partial data only, trying next layer")

    logger.info("[yt-dlp] Trying yt-dlp")
    if result := await scrape_ytdlp(url, identity):
        if is_usable_result(result):
            logger.info(f"[yt-dlp] Success — @{result.username}")
            return result

    return None


async def _finalize(
    result: ReelData,
    include_transcript: bool,
    include_ocr: bool,
) -> ReelData:
    if include_transcript:
        from app.scrapers.transcriber import enrich_with_transcript
        result = await enrich_with_transcript(result)
    if include_ocr:
        from app.scrapers.ocr import enrich_with_ocr
        result = await enrich_with_ocr(result)
    return result
