from fastapi import APIRouter, HTTPException
from app.models.schemas import ScrapeRequest, ScrapeResponse
from app.scrapers.orchestrator import scrape_reel

router = APIRouter()


@router.post("/scrape", response_model=ScrapeResponse)
async def scrape(req: ScrapeRequest):
    url = req.url.strip()

    if "instagram.com" not in url:
        raise HTTPException(status_code=400, detail="Must be an Instagram URL.")

    result = await scrape_reel(
        url,
        include_transcript=req.include_transcript,
        include_ocr=req.include_ocr,
    )

    if not result:
        return ScrapeResponse(success=False, error="All scraping layers failed. The Reel may be private or Instagram may be blocking requests.")

    return ScrapeResponse(success=True, data=result)


@router.get("/scrape")
async def scrape_get(
    url: str,
    include_transcript: bool = False,
    include_ocr: bool = False,
):
    """Convenience GET endpoint — useful for quick testing in the browser."""
    result = await scrape_reel(
        url,
        include_transcript=include_transcript,
        include_ocr=include_ocr,
    )
    if not result:
        raise HTTPException(status_code=422, detail="Could not scrape this Reel.")
    return result


@router.get("/health")
async def health():
    return {"status": "ok"}
