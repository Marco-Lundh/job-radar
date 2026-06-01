from collections.abc import AsyncIterator
from datetime import UTC, datetime

from pydantic_ai import Agent

import storage
from agents._utils import RATE_LIMIT_MSG, _is_rate_limit, _sse
from config import make_groq_model
from models import AppSettings, Job, Profile, RankerOutput, SearchConfig


def _build_prompt(
    job_title: str,
    job_description: str,
    profile: Profile,
    work_type_filter: list[str],
    ui_language: str,
) -> str:
    filter_note = (
        f"The user prefers work types: {', '.join(work_type_filter)}."
        if work_type_filter
        else "The user has no work type preference."
    )
    return (
        f"You are evaluating a job posting for a candidate."
        f' Respond in language "{ui_language}" (BCP-47).\n\n'
        f"CANDIDATE PROFILE:\n"
        f"- Desired title: {profile.desired_title}\n"
        f"- Location: {profile.location}\n"
        f"- Skills: {', '.join(profile.skills)}\n"
        f"- Experience: {profile.experience_years} years\n"
        f"- Summary: {profile.summary}\n\n"
        f"WORK TYPE PREFERENCE: {filter_note}\n\n"
        f"JOB TITLE: {job_title}\n\n"
        f"JOB DESCRIPTION:\n{job_description[:3000]}\n\n"
        f"Evaluate and return:\n"
        f"1. relevance_score (0-100): how well the job matches the"
        f" candidate's profile. Penalise work-type mismatches.\n"
        f"2. relevance_reason: one or two sentences explaining the score.\n"
        f"3. work_type: detect from the description — one of"
        f' "remote", "hybrid", "on-site", or "unknown".'
    )


async def run_ranker_agent(
    profile: Profile,
    config: SearchConfig,
    app_settings: AppSettings,
    job_id: str | None = None,
) -> AsyncIterator[str]:
    agent: Agent[None, RankerOutput] = Agent(
        make_groq_model(),
        output_type=RankerOutput,
    )

    jobs = storage.load_jobs()
    if job_id:
        jobs = [j for j in jobs if j.id == job_id]
    else:
        jobs = [j for j in jobs if j.relevance_score is None]

    if not jobs:
        yield _sse({"type": "progress", "message": "No unranked jobs."})
        yield _sse({"type": "done"})
        return

    yield _sse(
        {
            "type": "progress",
            "message": f"Ranking {len(jobs)} job(s)...",
        }
    )

    updated_jobs: list[Job] = []
    for job in jobs:
        yield _sse(
            {
                "type": "progress",
                "message": f"Ranking: {job.title} at {job.company}",
            }
        )
        try:
            result = await agent.run(
                _build_prompt(
                    job.title,
                    job.description,
                    profile,
                    list(config.work_type),
                    app_settings.ui_language,
                )
            )
            output = result.output
            job.relevance_score = output.relevance_score
            job.relevance_reason = output.relevance_reason
            job.work_type = output.work_type
            job.ranked_at = datetime.now(UTC).isoformat()
            updated_jobs.append(job)
            yield _sse(
                {
                    "type": "progress",
                    "message": (
                        f"{job.title}: score {output.relevance_score}"
                        f" ({output.work_type})"
                    ),
                    "job_id": job.id,
                    "relevance_score": output.relevance_score,
                    "work_type": output.work_type,
                }
            )
        except Exception as exc:
            if _is_rate_limit(exc):
                yield _sse(
                    {
                        "type": "error",
                        "message": RATE_LIMIT_MSG,
                    }
                )
                break
            yield _sse(
                {
                    "type": "error",
                    "message": str(exc),
                    "job_id": job.id,
                }
            )

    if updated_jobs:
        storage.batch_upsert_jobs(updated_jobs)
    yield _sse({"type": "done"})
