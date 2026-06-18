"""Realistic header builders — mirrors what Apify sends to stay unblocked."""

import random

from fake_useragent import UserAgent

from app.core.config import INSTAGRAM_APP_ID, MOBILE_HEADERS
from app.scrapers.identity_pool import ScrapeIdentity

_ua = UserAgent(browsers=["chrome", "safari"], os=["ios", "android"])

MOBILE_USER_AGENTS = [
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
        "Mozilla/5.0 (Linux; Android 13; SM-S911B) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Mobile Safari/537.36"
    ),
]

INSTAGRAM_APP_USER_AGENTS = [
    "Instagram 359.0.0.0.0 Android (33/13; 420dpi; 1080x2400; samsung; SM-S911B; dm1q; qcom; en_US; 666146327)",
    "Instagram 358.0.0.0.0 Android (34/14; 480dpi; 1080x2400; Google; Pixel 8; shiba; google; en_US; 665014110)",
    "Instagram 357.0.0.0.0 Android (33/13; 440dpi; 1080x2400; OnePlus; CPH2449; OP594DL1; qcom; en_US; 664229427)",
]


def _random_mobile_ua() -> str:
    return random.choice(MOBILE_USER_AGENTS)


def _cookie_header(session_id: str | None) -> str | None:
    if not session_id:
        return None
    return f"sessionid={session_id}"


def build_web_headers(identity: ScrapeIdentity) -> dict:
    headers = MOBILE_HEADERS.copy()
    headers["User-Agent"] = _random_mobile_ua()
    if cookie := _cookie_header(identity.session_id):
        headers["Cookie"] = cookie
    return headers


def build_mobile_api_headers(referer: str, identity: ScrapeIdentity) -> dict:
    headers = {
        "User-Agent": random.choice(INSTAGRAM_APP_USER_AGENTS),
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "X-IG-App-ID": INSTAGRAM_APP_ID,
        "X-ASBD-ID": "129477",
        "X-IG-WWW-Claim": "0",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Referer": referer,
        "Origin": "https://www.instagram.com",
    }
    if cookie := _cookie_header(identity.session_id):
        headers["Cookie"] = cookie
    return headers
