"""
Scraper orchestrator.
Tries each layer in order — HTTP → Playwright → yt-dlp.
Returns the first successful result.
"""

import logging
from app.models.schemas import ReelData
from app.scrapers.http_scraper import scrape_http
from app.scrapers.playwright_scraper import scrape_playwright
from app.scrapers.ytdlp_scraper import scrape_ytdlp

logger = logging.getLogger(__name__)


async def scrape_reel(url: str) -> ReelData | None:
    # Layer 1: fast raw HTTP
    logger.info(f"[HTTP] Trying {url}")
    result = await scrape_http(url)
    if result:
        logger.info(f"[HTTP] Success — @{result.username}")
        return result

    # Layer 2: headless browser
    logger.info(f"[Playwright] HTTP failed, trying browser")
    result = await scrape_playwright(url)
    if result:
        logger.info(f"[Playwright] Success — @{result.username}")
        return result

    # Layer 3: yt-dlp
    logger.info(f"[yt-dlp] Playwright failed, trying yt-dlp")
    result = await scrape_ytdlp(url)
    if result:
        logger.info(f"[yt-dlp] Success — @{result.username}")
        return result

    logger.warning(f"All layers failed for {url}")
    return None
