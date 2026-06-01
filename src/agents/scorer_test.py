import json
from unittest.mock import AsyncMock, MagicMock

import pydantic_ai

import storage
from agents.scorer import _build_prompt, run_scorer_agent
from models import Job, Profile, ScoreOutput


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


def _mock_scorer(monkeypatch, output: ScoreOutput) -> None:
    result = MagicMock()
    result.output = output
    monkeypatch.setattr(
        pydantic_ai.Agent, "run", AsyncMock(return_value=result)
    )


def _score_output(**kwargs) -> ScoreOutput:
    defaults = {
        "fit_score": 75,
        "strengths": ["Strong Python skills"],
        "weaknesses": ["No Java experience"],
        "recommendations": ["Highlight FastAPI projects"],
        "fit_summary": "Good overall fit.",
    }
    return ScoreOutput(**{**defaults, **kwargs})


# --- _build_prompt ---


def test_prompt_contains_job_title():
    assert "Senior Dev" in _build_prompt(
        "Senior Dev", "Job description here", "My CV text"
    )


def test_prompt_contains_cv_text():
    assert "My unique CV content here" in _build_prompt(
        "Dev", "description", "My unique CV content here"
    )


def test_prompt_truncates_description_to_3000_chars():
    prompt = _build_prompt("Dev", "a" * 4000, "CV")
    assert "a" * 3000 in prompt
    assert "a" * 3001 not in prompt


def test_prompt_truncates_cv_to_3000_chars():
    prompt = _build_prompt("Dev", "desc", "b" * 4000)
    assert "b" * 3000 in prompt
    assert "b" * 3001 not in prompt


def test_prompt_mentions_fit_score():
    assert "fit_score" in _build_prompt("Dev", "desc", "cv")


def test_prompt_mentions_strengths_and_weaknesses():
    prompt = _build_prompt("Dev", "desc", "cv")
    assert "strengths" in prompt
    assert "weaknesses" in prompt


def test_prompt_mentions_recommendations():
    assert "recommendations" in _build_prompt("Dev", "desc", "cv")


# --- run_scorer_agent ---


async def test_scorer_emits_error_when_job_not_found(tmp_data):
    events = await _collect(
        run_scorer_agent("missing-id", Profile(cv_text="My CV"))
    )
    assert events[0]["type"] == "error"
    assert "not found" in events[0]["message"].lower()


async def test_scorer_emits_error_when_no_cv(tmp_data):
    storage.save_jobs([_make_job(id="j1")])
    events = await _collect(run_scorer_agent("j1", Profile()))
    assert events[0]["type"] == "error"
    assert "cv" in events[0]["message"].lower()


async def test_scorer_uses_summary_when_no_cv_text(tmp_data, monkeypatch):
    _mock_scorer(monkeypatch, _score_output())
    storage.save_jobs([_make_job(id="j1")])
    events = await _collect(
        run_scorer_agent("j1", Profile(summary="Experienced dev"))
    )
    assert events[-1]["type"] == "done"


async def test_scorer_saves_result_to_job(tmp_data, monkeypatch):
    _mock_scorer(monkeypatch, _score_output(fit_score=88))
    storage.save_jobs([_make_job(id="j1")])

    await _collect(run_scorer_agent("j1", Profile(cv_text="My detailed CV")))

    job = storage.get_job("j1")
    assert job is not None
    assert job.fit_score == 88
    assert job.strengths == ["Strong Python skills"]
    assert job.weaknesses == ["No Java experience"]
    assert job.recommendations == ["Highlight FastAPI projects"]
    assert job.fit_summary == "Good overall fit."
    assert job.scored_at is not None


async def test_scorer_done_event_contains_fit_score(tmp_data, monkeypatch):
    _mock_scorer(monkeypatch, _score_output(fit_score=72))
    storage.save_jobs([_make_job(id="j1")])

    events = await _collect(run_scorer_agent("j1", Profile(cv_text="CV")))

    done = events[-1]
    assert done["type"] == "done"
    assert done["fit_score"] == 72
    assert done["job_id"] == "j1"


async def test_scorer_emits_error_on_rate_limit(tmp_data, monkeypatch):
    monkeypatch.setattr(
        pydantic_ai.Agent,
        "run",
        AsyncMock(side_effect=Exception("429 rate limit")),
    )
    storage.save_jobs([_make_job(id="j1")])

    events = await _collect(run_scorer_agent("j1", Profile(cv_text="CV")))

    errors = [e for e in events if e["type"] == "error"]
    assert errors
    assert "rate limit" in errors[0]["message"].lower()


async def test_scorer_emits_error_on_generic_exception(tmp_data, monkeypatch):
    monkeypatch.setattr(
        pydantic_ai.Agent,
        "run",
        AsyncMock(side_effect=Exception("model timeout")),
    )
    storage.save_jobs([_make_job(id="j1")])

    events = await _collect(run_scorer_agent("j1", Profile(cv_text="CV")))

    errors = [e for e in events if e["type"] == "error"]
    assert "model timeout" in errors[0]["message"]
