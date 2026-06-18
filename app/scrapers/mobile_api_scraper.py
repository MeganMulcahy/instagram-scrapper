"""
Layer 2: Instagram internal mobile API.
Hits the same JSON endpoints the iPhone/Android app calls.
"""

import json

import httpx

from app.models.schemas import ReelData
from app.scrapers.headers import build_mobile_api_headers
from app.scrapers.identity_pool import ScrapeIdentity
from app.scrapers.parsers import (
    extract_shortcode,
    find_media,
    parse_mobile_api_item,
    parse_web_media,
    shortcode_to_media_id,
)

_GRAPHQL_DOC_ID = "8845758582119845"


async def scrape_mobile_api(url: str, identity: ScrapeIdentity) -> ReelData | None:
    shortcode = extract_shortcode(url)
    if not shortcode:
        return None

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=20,
        proxy=identity.proxy_url,
        http2=True,
    ) as client:
        result = await _try_rest_api(client, url, shortcode, identity)
        if result:
            return result
        return await _try_graphql(client, url, shortcode, identity)


async def _try_rest_api(
    client: httpx.AsyncClient,
    url: str,
    shortcode: str,
    identity: ScrapeIdentity,
) -> ReelData | None:
    media_id = shortcode_to_media_id(shortcode)
    endpoints = [
        f"https://i.instagram.com/api/v1/media/{media_id}/info/",
        f"https://www.instagram.com/api/v1/media/{media_id}/info/",
    ]

    for endpoint in endpoints:
        headers = build_mobile_api_headers(url, identity)
        try:
            resp = await client.get(endpoint, headers=headers)
        except httpx.RequestError:
            continue

        if resp.status_code != 200:
            continue

        try:
            data = resp.json()
        except json.JSONDecodeError:
            continue

        items = data.get("items") or []
        if items:
            try:
                return parse_mobile_api_item(items[0], url)
            except (KeyError, TypeError, IndexError):
                continue

        if media := find_media(data):
            try:
                return parse_mobile_api_item(media, url)
            except (KeyError, TypeError, IndexError):
                continue

    return None


async def _try_graphql(
    client: httpx.AsyncClient,
    url: str,
    shortcode: str,
    identity: ScrapeIdentity,
) -> ReelData | None:
    headers = build_mobile_api_headers(url, identity)
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    variables = json.dumps({"shortcode": shortcode})

    try:
        resp = await client.post(
            "https://www.instagram.com/graphql/query/",
            headers=headers,
            data={"variables": variables, "doc_id": _GRAPHQL_DOC_ID},
        )
    except httpx.RequestError:
        return None

    if resp.status_code != 200:
        return None

    try:
        data = resp.json()
    except json.JSONDecodeError:
        return None

    media = find_media(data)
    if not media:
        return None

    return parse_web_media(media, url, scraped_via="mobile_api")
