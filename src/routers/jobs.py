import shutil
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

import storage
from config import settings as app_settings
from models import Job, JobPatch

router = APIRouter(tags=["Jobs"])


@router.get("/jobs", response_model=list[Job])
def list_jobs(
    status: (
        Literal["new", "interesting", "applied", "dismissed"] | None
    ) = None,
    min_score: int | None = Query(None, ge=0, le=100),
    source: str | None = None,
    work_type: list[Literal["remote", "hybrid", "on-site", "unknown"]] = Query(
        default=[]
    ),
) -> list[Job]:
    """
    List all jobs with optional filters.
    work_type is repeatable: ?work_type=remote&work_type=hybrid
    """
    jobs = storage.load_jobs()
    if status:
        jobs = [j for j in jobs if j.status == status]
    if min_score is not None:
        jobs = [
            j
            for j in jobs
            if j.relevance_score is not None and j.relevance_score >= min_score
        ]
    if source:
        jobs = [j for j in jobs if j.source == source]
    if work_type:
        jobs = [j for j in jobs if j.work_type in work_type]
    return jobs


@router.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: str) -> Job:
    """Return a single job by ID."""
    job = storage.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@router.patch("/jobs/{job_id}", response_model=Job)
def patch_job(job_id: str, body: JobPatch) -> Job:
    """Update job status or notes."""
    job = storage.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if body.status is not None:
        job.status = body.status
    if body.notes is not None:
        job.notes = body.notes
    storage.upsert_job(job)
    return job


@router.delete("/jobs")
def delete_all_jobs(confirm: bool = Query(False)) -> dict[str, bool]:
    """
    Delete all jobs. Pass ?confirm=true to execute.
    Also removes all saved cover letters.
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Pass ?confirm=true to delete all jobs.",
        )

    storage.save_jobs([])

    shutil.rmtree(app_settings.cover_letters_dir, ignore_errors=True)
    return {"deleted": True}
