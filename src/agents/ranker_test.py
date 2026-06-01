import json
from unittest.mock import AsyncMock, MagicMock

import pydantic_ai

import storage
from agents.ranker import _build_prompt, run_ranker_agent
from models import AppSettings, Job, Profile, RankerOutput, SearchConfig


def _profile(**kwargs) -> Profile:
    defaults = {
        "desired_title": "Backend Developer",
        "location": "Stockholm",
        "skills": ["Python", "FastAPI"],
        "experience_years": 4,
        "languages": ["Swedish", "English"],
        "summary": "Experienced backend developer.",
    }
    return Profile(**{**defaults, **kwargs})


def _make_job(**kwargs) -> Job:
    defaults = {
        "id": "job-1",
        "source": "platsbanken",
        "title": "Python Developer",
        "company": "Acme AB",
        "location": "Stockholm",
        "description": "We are looking for a Python developer.",
        "url": "https://example.com/jobs/1",
        "scraped_at": "2026-01-01T00:00:00Z",
    }
    return Job(**{**defaults, **kwargs})


async def _collect(agen) -> list[dict]:
    return [json.loads(raw.removeprefix("data: ")) async for raw in agen]


def _mock_ranker(monkeypatch, output: RankerOutput) -> None:
    result = MagicMock()
    result.output = output
    monkeypatch.setattr(
        pydantic_ai.Agent, "run", AsyncMock(return_value=result)
    )


# --- _build_prompt ---


def test_prompt_contains_job_title():
    assert "Senior Dev" in _build_prompt(
        "Senior Dev", "desc", _profile(), [], "en"
    )


def test_prompt_contains_candidate_skills():
    prompt = _build_prompt(
        "Dev", "desc", _profile(skills=["Rust", "Go"]), [], "en"
    )
    assert "Rust" in prompt
    assert "Go" in prompt


def test_prompt_contains_experience_years():
    assert "7" in _build_prompt(
        "Dev", "desc", _profile(experience_years=7), [], "en"
    )


def test_prompt_includes_work_type_preference():
    prompt = _build_prompt(
        "Dev", "desc", _profile(), ["remote", "hybrid"], "en"
    )
    assert "remote" in prompt
    assert "hybrid" in prompt


def test_prompt_no_preference_when_empty_work_type():
    assert (
        "no work type preference"
        in _build_prompt("Dev", "desc", _profile(), [], "en").lower()
    )


def test_prompt_includes_ui_language():
    assert '"sv"' in _build_prompt("Dev", "desc", _profile(), [], "sv")


def test_prompt_truncates_description_to_3000_chars():
    prompt = _build_prompt("Dev", "a" * 4000, _profile(), [], "en")
    assert "a" * 3000 in prompt
    assert "a" * 3001 not in prompt


def test_prompt_contains_profile_location():
    assert "Gothenburg" in _build_prompt(
        "Dev", "desc", _profile(location="Gothenburg"), [], "en"
    )


def test_prompt_contains_profile_summary():
    assert "Passionate coder" in _build_prompt(
        "Dev", "desc", _profile(summary="Passionate coder"), [], "en"
    )


# --- run_ranker_agent ---


async def test_ranker_emits_done_when_no_unranked_jobs(tmp_data):
    storage.save_jobs([_make_job(id="j1", relevance_score=80)])
    events = await _collect(
        run_ranker_agent(_profile(), SearchConfig(), AppSettings())
    )
    assert events[-1]["type"] == "done"
    assert any("No unranked jobs" in e.get("message", "") for e in events)


async def test_ranker_ranks_job_and_saves_result(tmp_data, monkeypatch):
    _mock_ranker(
        monkeypatch,
        RankerOutput(
            relevance_score=80,
            relevance_reason="Good match",
            work_type="remote",
        ),
    )
    storage.save_jobs([_make_job(id="j1")])

    events = await _collect(
        run_ranker_agent(_profile(), SearchConfig(), AppSettings())
    )

    assert events[-1]["type"] == "done"
    job = storage.get_job("j1")
    assert job is not None
    assert job.relevance_score == 80
    assert job.relevance_reason == "Good match"
    assert job.work_type == "remote"
    assert job.ranked_at is not None


async def test_ranker_skips_already_ranked_jobs(tmp_data, monkeypatch):
    _mock_ranker(
        monkeypatch,
        RankerOutput(
            relevance_score=50, relevance_reason="Meh", work_type="hybrid"
        ),
    )
    storage.save_jobs(
        [
            _make_job(id="j1"),
            _make_job(id="j2", relevance_score=90),
        ]
    )

    await _collect(run_ranker_agent(_profile(), SearchConfig(), AppSettings()))

    j2 = storage.get_job("j2")
    assert j2 is not None
    assert j2.relevance_score == 90


async def test_ranker_single_job_id_targets_only_that_job(
    tmp_data, monkeypatch
):
    _mock_ranker(
        monkeypatch,
        RankerOutput(
            relevance_score=60, relevance_reason="OK", work_type="on-site"
        ),
    )
    storage.save_jobs([_make_job(id="j1"), _make_job(id="j2")])

    await _collect(
        run_ranker_agent(
            _profile(), SearchConfig(), AppSettings(), job_id="j1"
        )
    )

    j1 = storage.get_job("j1")
    j2 = storage.get_job("j2")
    assert j1 is not None
    assert j2 is not None
    assert j1.relevance_score == 60
    assert j2.relevance_score is None


async def test_ranker_emits_error_on_rate_limit(tmp_data, monkeypatch):
    monkeypatch.setattr(
        pydantic_ai.Agent,
        "run",
        AsyncMock(side_effect=Exception("429 rate limit exceeded")),
    )
    storage.save_jobs([_make_job(id="j1")])

    events = await _collect(
        run_ranker_agent(_profile(), SearchConfig(), AppSettings())
    )

    errors = [e for e in events if e["type"] == "error"]
    assert errors
    assert "rate limit" in errors[0]["message"].lower()


async def test_ranker_emits_error_on_generic_exception(tmp_data, monkeypatch):
    monkeypatch.setattr(
        pydantic_ai.Agent,
        "run",
        AsyncMock(side_effect=Exception("something broke")),
    )
    storage.save_jobs([_make_job(id="j1")])

    events = await _collect(
        run_ranker_agent(_profile(), SearchConfig(), AppSettings())
    )

    errors = [e for e in events if e["type"] == "error"]
    assert errors
    assert "something broke" in errors[0]["message"]
