"""
Transcribe spoken audio from a Reel video.
Free local Whisper — no API key needed.
"""

import asyncio
import logging
import tempfile
from pathlib import Path

from app.core.config import WHISPER_MODEL
from app.models.schemas import ReelData
from app.scrapers.video_utils import download_video, extract_audio

logger = logging.getLogger(__name__)
_whisper_model = None


async def enrich_with_transcript(data: ReelData) -> ReelData:
    if not data.video_url:
        logger.warning("No video_url — cannot transcribe")
        return data

    transcript = await transcribe_video_url(data.video_url)
    return data.model_copy(update={"transcript": transcript})


async def transcribe_video_url(video_url: str) -> str | None:
    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = Path(tmpdir) / "video.mp4"
        audio_path = Path(tmpdir) / "audio.wav"

        if not await download_video(video_url, video_path):
            return None

        if not extract_audio(video_path, audio_path):
            return None

        return await asyncio.to_thread(_transcribe_local_whisper, audio_path)


def _transcribe_local_whisper(audio_path: Path) -> str | None:
    global _whisper_model
    try:
        import whisper
    except ImportError:
        logger.warning("Whisper not installed. Run: pip install openai-whisper")
        return None

    try:
        if _whisper_model is None:
            logger.info(f"Loading Whisper model '{WHISPER_MODEL}' (first run downloads ~150MB)...")
            _whisper_model = whisper.load_model(WHISPER_MODEL)

        result = _whisper_model.transcribe(str(audio_path), fp16=False, language="en")
        text = (result.get("text") or "").strip()
        return text or None
    except Exception as e:
        logger.warning(f"Whisper transcription failed: {e}")
        return None
