from typing import Literal

from pydantic import BaseModel

ScrapedVia = Literal["http", "mobile_api", "playwright", "ytdlp"]


class ReelData(BaseModel):
    url: str
    shortcode: str
    username: str
    caption: str
    hashtags: list[str] = []
    video_url: str | None = None
    thumbnail_url: str | None = None
    duration: float | None = None
    views: int | None = None
    likes: int | None = None
    audio_name: str | None = None
    transcript: str | None = None
    on_screen_text: list[str] = []
    scraped_via: ScrapedVia


class ScrapeRequest(BaseModel):
    url: str
    include_transcript: bool = False
    include_ocr: bool = False


class ScrapeResponse(BaseModel):
    success: bool
    data: ReelData | None = None
    error: str | None = None
