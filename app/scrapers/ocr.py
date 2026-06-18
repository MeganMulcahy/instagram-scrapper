"""
Extract on-screen text from Reel video frames (OCR).
Uses free local AI — EasyOCR by default, optional Ollama vision.
"""

import asyncio
import base64
import logging
import re
import tempfile
from pathlib import Path

import httpx

from app.core.config import OLLAMA_URL, OLLAMA_VISION_MODEL
from app.models.schemas import ReelData
from app.scrapers.video_utils import download_video, extract_frames

logger = logging.getLogger(__name__)
_easyocr_reader = None


async def enrich_with_ocr(data: ReelData) -> ReelData:
    if not data.video_url:
        logger.warning("No video_url — cannot run OCR")
        return data

    on_screen_text = await extract_on_screen_text(data.video_url)
    return data.model_copy(update={"on_screen_text": on_screen_text})


async def extract_on_screen_text(video_url: str) -> list[str]:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        video_path = tmp / "video.mp4"
        frames_dir = tmp / "frames"

        if not await download_video(video_url, video_path):
            return []

        frames = extract_frames(video_path, frames_dir)
        if not frames:
            return []

        return await asyncio.to_thread(_ocr_frames, frames)


def _ocr_frames(frames: list[Path]) -> list[str]:
    if OLLAMA_VISION_MODEL:
        results = _ocr_ollama(frames)
        if results:
            return results
        logger.info("Ollama OCR returned nothing — falling back to EasyOCR")

    results = _ocr_easyocr(frames)
    if results:
        return results

    logger.info("EasyOCR returned nothing — falling back to Tesseract")
    return _ocr_tesseract(frames)


def _ocr_easyocr(frames: list[Path]) -> list[str]:
    global _easyocr_reader
    try:
        import easyocr
    except ImportError:
        logger.warning("EasyOCR not installed. Run: pip install easyocr")
        return []

    try:
        if _easyocr_reader is None:
            logger.info("Loading EasyOCR model (first run downloads ~100MB)...")
            _easyocr_reader = easyocr.Reader(["en"], gpu=False, verbose=False)

        seen: set[str] = set()
        results: list[str] = []

        for frame in frames:
            detections = _easyocr_reader.readtext(str(frame))
            line_parts: dict[int, list[str]] = {}

            for _bbox, text, conf in detections:
                text = text.strip()
                if conf < 0.45 or len(text) < 2:
                    continue
                y_center = int((_bbox[0][1] + _bbox[2][1]) / 2)
                row = y_center // 30
                line_parts.setdefault(row, []).append(text)

            for parts in line_parts.values():
                line = " ".join(parts)
                for cleaned in _clean_lines(line):
                    key = cleaned.lower()
                    if key not in seen:
                        seen.add(key)
                        results.append(cleaned)

        return results
    except Exception as e:
        logger.warning(f"EasyOCR failed: {e}")
        return []


def _ocr_ollama(frames: list[Path]) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []

    step = max(1, len(frames) // 6)
    sampled = frames[::step][:6]

    prompt = (
        "List every piece of readable text visible in this video frame. "
        "One item per line. Only output the text — no commentary."
    )

    try:
        with httpx.Client(timeout=120) as client:
            for frame in sampled:
                try:
                    resp = client.post(
                        f"{OLLAMA_URL.rstrip('/')}/api/generate",
                        json={
                            "model": OLLAMA_VISION_MODEL,
                            "prompt": prompt,
                            "images": [base64.b64encode(frame.read_bytes()).decode()],
                            "stream": False,
                        },
                    )
                    resp.raise_for_status()
                    raw = resp.json().get("response", "")
                except Exception as e:
                    logger.warning(f"Ollama OCR failed on {frame.name}: {e}")
                    continue

                for line in _clean_lines(raw):
                    key = line.lower()
                    if key not in seen:
                        seen.add(key)
                        results.append(line)
    except Exception as e:
        logger.warning(f"Ollama not reachable at {OLLAMA_URL}: {e}")

    return results


def _ocr_tesseract(frames: list[Path]) -> list[str]:
    try:
        import pytesseract
        from PIL import Image, ImageEnhance, ImageFilter
    except ImportError:
        return []

    seen: set[str] = set()
    results: list[str] = []

    for frame in frames:
        try:
            img = Image.open(frame)
            img = img.convert("L")
            img = ImageEnhance.Contrast(img).enhance(2.5)
            img = img.filter(ImageFilter.SHARPEN)
            w, h = img.size
            img = img.resize((w * 2, h * 2), Image.LANCZOS)

            data = pytesseract.image_to_data(
                img, config="--psm 6", output_type=pytesseract.Output.DICT,
            )
            line_words: dict[tuple[int, int], list[str]] = {}

            for i, word in enumerate(data["text"]):
                word = word.strip()
                if not word:
                    continue
                try:
                    conf = int(data["conf"][i])
                except ValueError:
                    continue
                if conf < 55:
                    continue
                key = (data["block_num"][i], data["line_num"][i])
                line_words.setdefault(key, []).append(word)

            for words in line_words.values():
                for cleaned in _clean_lines(" ".join(words)):
                    k = cleaned.lower()
                    if k not in seen:
                        seen.add(k)
                        results.append(cleaned)
        except Exception:
            continue

    return results


def _clean_lines(text: str) -> list[str]:
    lines: list[str] = []
    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if len(line) < 3:
            continue
        if not re.search(r"[a-zA-Z]{3}", line):
            continue
        alpha = sum(c.isalpha() for c in line)
        if alpha / len(line) < 0.4:
            continue
        lines.append(line)
    return lines
