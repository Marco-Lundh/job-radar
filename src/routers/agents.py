from fastapi import APIRouter
from fastapi.responses import StreamingResponse

import storage
from agents.cover_letter import run_cover_letter_agent
from agents.ranker import run_ranker_agent
from agents.scorer import run_scorer_agent
from agents.scraper import run_scraper_agent
from models import CoverLetterGenerateRequest

_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}

router = APIRouter(prefix="/agents", tags=["Agents"])


@router.post("/scrape")
async def scrape() -> StreamingResponse:
    """
    Run ScraperAgent using the current search config.
    Returns a Server-Sent Events stream of progress events.
    """
    config = storage.load_search_config()
    return StreamingResponse(
        run_scraper_agent(config),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.post("/rank")
async def rank_all() -> StreamingResponse:
    """
    Run RankerAgent on all unranked jobs.
    Detects work_type per job as part of the same LLM call.
    Returns a Server-Sent Events stream.
    """
    profile = storage.load_profile()
    config = storage.load_search_config()
    app_settings = storage.load_app_settings()
    return StreamingResponse(
        run_ranker_agent(profile, config, app_settings),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.post("/rank/{job_id}")
async def rank_single(job_id: str) -> StreamingResponse:
    """Re-run RankerAgent for a single job."""
    profile = storage.load_profile()
    config = storage.load_search_config()
    app_settings = storage.load_app_settings()
    return StreamingResponse(
        run_ranker_agent(profile, config, app_settings, job_id=job_id),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.post("/score/{job_id}")
async def score(job_id: str) -> StreamingResponse:
    """Run ScorerAgent for a single job to produce a CV-fit analysis."""
    profile = storage.load_profile()
    return StreamingResponse(
        run_scorer_agent(job_id, profile),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.post("/cover-letter/{job_id}")
async def generate_cover_letter(
    job_id: str,
    body: CoverLetterGenerateRequest,
) -> StreamingResponse:
    """
    Run CoverLetterAgent for a specific job.
    The letter is written in the job's detected language.
    """
    profile = storage.load_profile()
    return StreamingResponse(
        run_cover_letter_agent(job_id, profile, body.hints),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
