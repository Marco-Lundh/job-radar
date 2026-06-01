from collections.abc import AsyncIterator
from datetime import UTC, datetime

from pydantic_ai import Agent

import storage
from agents._utils import RATE_LIMIT_MSG, _is_rate_limit, _sse
from config import make_groq_model
from models import Profile, ScoreOutput


def _build_prompt(
    job_title: str,
    job_description: str,
    cv_text: str,
) -> str:
    return f"""
You are a senior recruiter performing a detailed CV-fit analysis.

JOB TITLE: {job_title}

JOB DESCRIPTION:
{job_description[:3000]}

CANDIDATE CV:
{cv_text[:3000]}

Return a structured analysis with:
- fit_score (0-100)
- strengths: list of strings — what makes the candidate a good fit
- weaknesses: list of strings — gaps or mismatches
- recommendations: list of strings — actions to improve the application
- fit_summary: 2-3 sentence overall assessment
""".strip()


async def run_scorer_agent(
    job_id: str,
    profile: Profile,
) -> AsyncIterator[str]:
    job = storage.get_job(job_id)
    if not job:
        yield _sse({"type": "error", "message": f"Job {job_id} not found."})
        return

    cv_text = profile.cv_text or profile.summary
    if not cv_text:
        yield _sse(
            {
                "type": "error",
                "message": "No CV text found in profile.",
            }
        )
        return

    agent: Agent[None, ScoreOutput] = Agent(
        make_groq_model(), output_type=ScoreOutput
    )

    yield _sse(
        {
            "type": "progress",
            "message": f"Analysing fit for: {job.title}...",
        }
    )

    try:
        result = await agent.run(
            _build_prompt(job.title, job.description, cv_text)
        )
        output = result.output
        job.fit_score = output.fit_score
        job.strengths = output.strengths
        job.weaknesses = output.weaknesses
        job.recommendations = output.recommendations
        job.fit_summary = output.fit_summary
        job.scored_at = datetime.now(UTC).isoformat()
        storage.upsert_job(job)
        yield _sse(
            {
                "type": "done",
                "job_id": job_id,
                "fit_score": output.fit_score,
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
        else:
            yield _sse({"type": "error", "message": str(exc)})
