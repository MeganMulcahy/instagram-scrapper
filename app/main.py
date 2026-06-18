import logging

from fastapi import FastAPI

from app.api.routes import router

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Instagram Reel Scraper",
    description="Three-layer Instagram Reel scraper: HTTP → Playwright → yt-dlp",
    version="1.0.0",
)

app.include_router(router)
