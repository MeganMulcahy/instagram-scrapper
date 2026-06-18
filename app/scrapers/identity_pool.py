"""
Session + proxy pool for production scaling.

Sessions are optional — public scraping works without them.
Proxies are the main anti-block tool (residential IPs).
"""

import asyncio
import random
import time
from dataclasses import dataclass

from app.core.config import (
    INSTAGRAM_SESSION_ID,
    PROXY_URL,
    REQUEST_DELAY_MAX,
    REQUEST_DELAY_MIN,
    SESSION_IDS,
    PROXY_URLS,
)


@dataclass(frozen=True)
class ScrapeIdentity:
    session_id: str | None
    proxy_url: str | None
    label: str


def _build_identities() -> list[ScrapeIdentity]:
    sessions = list(SESSION_IDS)
    if not sessions and INSTAGRAM_SESSION_ID:
        sessions = [INSTAGRAM_SESSION_ID]

    proxies = list(PROXY_URLS)
    if not proxies and PROXY_URL:
        proxies = [PROXY_URL]

    count = max(len(sessions), len(proxies), 1)
    identities: list[ScrapeIdentity] = []

    for i in range(count):
        session = sessions[i % len(sessions)] if sessions else None
        proxy = proxies[i % len(proxies)] if proxies else None
        identities.append(ScrapeIdentity(
            session_id=session,
            proxy_url=proxy,
            label=f"identity-{i + 1}",
        ))

    return identities


class IdentityPool:
    def __init__(self) -> None:
        self._identities = _build_identities()
        self._index = 0
        self._lock = asyncio.Lock()
        self._last_used: dict[str, float] = {}

    @property
    def size(self) -> int:
        return len(self._identities)

    async def acquire(self) -> ScrapeIdentity:
        async with self._lock:
            identity = self._identities[self._index % len(self._identities)]
            self._index += 1

            delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
            elapsed = time.monotonic() - self._last_used.get(identity.label, 0)
            if elapsed < delay:
                await asyncio.sleep(delay - elapsed)

            self._last_used[identity.label] = time.monotonic()
            return identity


identity_pool = IdentityPool()
