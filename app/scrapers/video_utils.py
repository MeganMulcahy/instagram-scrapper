"""Shared helpers for downloading and processing Reel videos."""

import logging
import subprocess
import tempfile
from pathlib import Path

import httpx

from app.core.config import INSTAGRAM_SESSION_ID

logger = logging.getLogger(__name__)


async def download_video(url: str, dest: Path) -> bool:
    headers = {}
    if INSTAGRAM_SESSION_ID:
        headers["Cookie"] = f"sessionid={INSTAGRAM_SESSION_ID}"

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=120,
            headers=headers,
        ) as client:
            async with client.stream("GET", url) as resp:
                if resp.status_code != 200:
                    logger.warning(f"Video download failed: HTTP {resp.status_code}")
                    return False
                with open(dest, "wb") as f:
                    async for chunk in resp.aiter_bytes():
                        f.write(chunk)
        return dest.stat().st_size > 0
    except httpx.RequestError as e:
        logger.warning(f"Video download failed: {e}")
        return False


def extract_audio(video: Path, audio: Path) -> bool:
    return _ffmpeg([
        "ffmpeg", "-y",
        "-i", str(video),
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        str(audio),
    ]) and audio.exists() and audio.stat().st_size > 0


def extract_frames(video: Path, output_dir: Path, fps: float = 1.0, max_frames: int = 30) -> list[Path]:
    """Extract JPEG frames from video for OCR."""
    output_dir.mkdir(parents=True, exist_ok=True)
    pattern = str(output_dir / "frame_%03d.jpg")

    ok = _ffmpeg([
        "ffmpeg", "-y",
        "-i", str(video),
        "-vf", f"fps={fps}",
        "-frames:v", str(max_frames),
        "-q:v", "2",
        pattern,
    ])

    if not ok:
        return []

    return sorted(output_dir.glob("frame_*.jpg"))


def _ffmpeg(cmd: list[str]) -> bool:
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except FileNotFoundError:
        logger.warning("ffmpeg not found — install with: brew install ffmpeg")
        return False
    except subprocess.CalledProcessError as e:
        logger.warning(f"ffmpeg failed: {e.stderr.decode(errors='ignore')[:200]}")
        return False
