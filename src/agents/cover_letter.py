import re
from collections.abc import AsyncIterator

from pydantic_ai import Agent

import storage
from agents._utils import RATE_LIMIT_MSG, _is_rate_limit, _sse
from config import make_groq_model
from models import Profile

_SWEDISH_MARKERS = {"och", "att", "för", "med", "som", "till", "av"}


def _build_prompt(
    job_title: str,
    job_company: str,
    job_description: str,
    job_language: str,
    cv_text: str,
    hints: str,
) -> str:
    hints_section = (
        f"\nADDITIONAL HINTS FROM CANDIDATE:\n{hints}" if hints else ""
    )
    return f"""
Write a professional cover letter in language "{job_language}" (BCP-47).

The letter should be addressed to {job_company} for the position: {job_title}.
It must be concise (3-4 paragraphs), compelling, and tailored to the job.
Do not include a subject line or date header — only the letter body.

JOB DESCRIPTION:
{job_description[:3000]}

CANDIDATE CV / SUMMARY:
{cv_text[:3000]}
{hints_section}
""".strip()


async def run_cover_letter_agent(
    job_id: str,
    profile: Profile,
    hints: str = "",
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

    # Detect language by Swedish word frequency; fall back to UI language
    app_s = storage.load_app_settings()
    job_language = app_s.ui_language
    words = re.findall(r"\b\w+\b", job.description.lower())
    if sum(1 for w in words if w in _SWEDISH_MARKERS) > 5:
        job_language = "sv"

    agent: Agent[None, str] = Agent(make_groq_model(), output_type=str)

    yield _sse(
        {
            "type": "progress",
            "message": f"Writing cover letter for: {job.title}...",
        }
    )

    try:
        result = await agent.run(
            _build_prompt(
                job.title,
                job.company,
                job.description,
                job_language,
                cv_text,
                hints,
            )
        )
        letter = result.output
        storage.save_cover_letter(job_id, letter)
        yield _sse(
            {
                "type": "done",
                "job_id": job_id,
                "text": letter,
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
