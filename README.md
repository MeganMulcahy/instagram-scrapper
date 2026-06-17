# instagram-scrapper

A production-grade Instagram Reel scraper built in Python. Uses a three-layer approach to maximize success rate while staying undetected — the same strategy used by commercial scrapers like Apify, rebuilt from scratch.

## How it works

Requests flow through three layers, each a fallback for the previous:

```
POST /scrape  { url }
      │
      ├─ Layer 1: Raw HTTP
      │   httpx + realistic mobile headers + JSON blob extraction
      │   Fast. No browser. Works for most public Reels.
      │
      ├─ Layer 2: Playwright (headless Chrome)
      │   Emulates iPhone 14 Pro. Intercepts GraphQL API responses.
      │   Used when Instagram returns a login wall or empty JSON.
      │
      └─ Layer 3: yt-dlp
          Battle-tested downloader as final fallback.
          Always gets the video URL if the Reel is public.
```

## Output schema

```json
{
  "url": "https://www.instagram.com/reel/...",
  "shortcode": "ABC123",
  "username": "gordonramsayofficial",
  "caption": "The secret to perfect pasta carbonara...",
  "hashtags": ["cooking", "pasta", "italian"],
  "video_url": "https://...",
  "thumbnail_url": "https://...",
  "duration": 28.5,
  "views": 4200000,
  "likes": 312000,
  "audio_name": "Original Audio",
  "scraped_via": "http"
}
```

## Setup

```bash
# Install dependencies
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Configure environment
cp .env.example .env
```

## Run locally

```bash
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

## Test a Reel

```bash
python scripts/test_scrape.py https://www.instagram.com/reel/SHORTCODE/
```

Or hit the API directly:
```bash
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.instagram.com/reel/SHORTCODE/"}'
```

## Deploy to Railway

```bash
railway login
railway link   # link to your Railway project
railway up
```

## Anti-detection strategy

- Rotates 4 realistic mobile user agents (iOS Safari + Android Chrome)
- Sends full browser header set including `Sec-Fetch-*` headers
- Random request delays (0.8–2.5s) to mimic human timing
- Playwright emulates iPhone 14 Pro device profile
- Hides automation fingerprints (`navigator.webdriver`)
- Optional residential proxy support via `PROXY_URL` env var

## Legal note

This scraper only accesses publicly visible content — the same data visible to a logged-out user in an incognito browser. A 2024 federal court ruling (Meta v. Bright Data) confirmed that scraping public web data does not violate the CFAA where no technological access barrier is bypassed.

# instagram-scrapper
