#!/usr/bin/env python3
"""Quick CLI test for the scraper orchestrator."""

import asyncio
import json
import sys

from app.scrapers.orchestrator import scrape_reel


async def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_scrape.py <instagram-reel-url> [--transcript] [--ocr]")
        sys.exit(1)

    url = sys.argv[1]
    include_transcript = "--transcript" in sys.argv
    include_ocr = "--ocr" in sys.argv
    print(f"Scraping: {url}")
    extras = []
    if include_transcript:
        extras.append("audio transcript")
    if include_ocr:
        extras.append("on-screen OCR")
    if extras:
        print(f"(with {' + '.join(extras)})\n")
    else:
        print()

    result = await scrape_reel(
        url,
        include_transcript=include_transcript,
        include_ocr=include_ocr,
    )

    if not result:
        print("FAILED — all layers returned nothing.")
        sys.exit(1)

    print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
