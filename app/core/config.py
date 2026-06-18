import os

from dotenv import load_dotenv

load_dotenv()


def _env_list(key: str) -> list[str]:
    raw = os.getenv(key, "")
    return [part.strip() for part in raw.split(",") if part.strip()]


# Legacy single-value vars (still supported)
PROXY_URL = os.getenv("PROXY_URL") or None
INSTAGRAM_SESSION_ID = os.getenv("INSTAGRAM_SESSION_ID") or None

# Production pools — comma-separated in .env
PROXY_URLS = _env_list("PROXY_URLS")
SESSION_IDS = _env_list("INSTAGRAM_SESSION_IDS")

INSTAGRAM_APP_ID = os.getenv("INSTAGRAM_APP_ID", "936619743392459")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")

# Free local vision AI (optional — install Ollama + pull a vision model)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL") or None

# Human-like timing between requests (seconds)
REQUEST_DELAY_MIN = float(os.getenv("REQUEST_DELAY_MIN", "2.0"))
REQUEST_DELAY_MAX = float(os.getenv("REQUEST_DELAY_MAX", "5.0"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

MOBILE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}
