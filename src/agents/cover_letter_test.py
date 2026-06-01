import json
from unittest.mock import AsyncMock, MagicMock

import pydantic_ai

import storage
from agents.cover_letter import _build_prompt, run_cover_letter_agent
from models import AppSettings, Job, Profile


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


def _mock_agent(monkeypatch, letter: str = "Dear Hiring Manager...") -> None:
    result = MagicMock()
    result.output = letter
    monkeypatch.setattr(
        pydantic_ai.Agent, "run", AsyncMock(return_value=result)
    )


# --- _build_prompt ---


def test_prompt_contains_company_and_title():
    prompt = _build_prompt(
        "Backend Dev", "Acme AB", "Job desc", "en", "My CV", ""
    )
    assert "Acme AB" in prompt
    assert "Backend Dev" in prompt


def test_prompt_contains_language_tag():
    prompt = _build_prompt("Dev", "Acme", "Job desc", "sv", "CV", "")
    assert '"sv"' in prompt


def test_prompt_includes_hints_when_provided():
    prompt = _build_prompt(
        "Dev", "Acme", "Job desc", "en", "CV", "Emphasize teamwork"
    )
    assert "Emphasize teamwork" in prompt


def test_prompt_no_hints_section_when_empty():
    prompt = _build_prompt("Dev", "Acme", "Job desc", "en", "CV", "")
    assert "ADDITIONAL HINTS" not in prompt


def test_prompt_truncates_description_to_3000_chars():
    prompt = _build_prompt("Dev", "Acme", "a" * 4000, "en", "CV", "")
    assert "a" * 3000 in prompt
    assert "a" * 3001 not in prompt


def test_prompt_truncates_cv_to_3000_chars():
    prompt = _build_prompt("Dev", "Acme", "desc", "en", "b" * 4000, "")
    assert "b" * 3000 in prompt
    assert "b" * 3001 not in prompt


def test_prompt_contains_cv_text():
    prompt = _build_prompt(
        "Dev", "Acme", "desc", "en", "Unique CV content", ""
    )
    assert "Unique CV content" in prompt


# --- run_cover_letter_agent ---


async def test_cover_letter_emits_error_when_job_not_found(tmp_data):
    events = await _collect(
        run_cover_letter_agent("missing-id", Profile(cv_text="CV"))
    )
    assert events[0]["type"] == "error"
    assert "not found" in events[0]["message"].lower()


async def test_cover_letter_emits_error_when_no_cv(tmp_data):
    storage.save_jobs([_make_job(id="j1")])
    events = await _collect(run_cover_letter_agent("j1", Profile()))
    assert events[0]["type"] == "error"
    assert "cv" in events[0]["message"].lower()


async def test_cover_letter_uses_summary_when_no_cv_text(
    tmp_data, monkeypatch
):
    _mock_agent(monkeypatch)
    storage.save_jobs([_make_job(id="j1")])
    events = await _collect(
        run_cover_letter_agent("j1", Profile(summary="Experienced dev"))
    )
    assert events[-1]["type"] == "done"


async def test_cover_letter_saves_letter_to_disk(tmp_data, monkeypatch):
    _mock_agent(monkeypatch, "The generated letter text.")
    storage.save_jobs([_make_job(id="j1")])

    await _collect(run_cover_letter_agent("j1", Profile(cv_text="My CV")))

    assert storage.load_cover_letter("j1") == "The generated letter text."


async def test_cover_letter_done_event_contains_text(tmp_data, monkeypatch):
    _mock_agent(monkeypatch, "Letter body here.")
    storage.save_jobs([_make_job(id="j1")])

    events = await _collect(
        run_cover_letter_agent("j1", Profile(cv_text="CV"))
    )

    done = events[-1]
    assert done["type"] == "done"
    assert done["text"] == "Letter body here."
    assert done["job_id"] == "j1"


async def test_cover_letter_detects_swedish_from_description(
    tmp_data, monkeypatch
):
    captured: list[str] = []

    async def _capture(self, prompt):
        captured.append(prompt)
        result = MagicMock()
        result.output = "Hej!"
        return result

    monkeypatch.setattr(pydantic_ai.Agent, "run", _capture)
    swedish_desc = (
        "Vi söker en utvecklare som och att för med som till av arbetar"
    )
    storage.save_jobs([_make_job(id="j1", description=swedish_desc)])
    storage.save_app_settings(AppSettings(ui_language="en"))

    await _collect(run_cover_letter_agent("j1", Profile(cv_text="CV")))

    assert '"sv"' in captured[0]


async def test_cover_letter_emits_error_on_rate_limit(tmp_data, monkeypatch):
    monkeypatch.setattr(
        pydantic_ai.Agent,
        "run",
        AsyncMock(side_effect=Exception("429 rate limit")),
    )
    storage.save_jobs([_make_job(id="j1")])

    events = await _collect(
        run_cover_letter_agent("j1", Profile(cv_text="CV"))
    )

    errors = [e for e in events if e["type"] == "error"]
    assert errors
    assert "rate limit" in errors[0]["message"].lower()


async def test_cover_letter_emits_error_on_generic_exception(
    tmp_data, monkeypatch
):
    monkeypatch.setattr(
        pydantic_ai.Agent,
        "run",
        AsyncMock(side_effect=Exception("network error")),
    )
    storage.save_jobs([_make_job(id="j1")])

    events = await _collect(
        run_cover_letter_agent("j1", Profile(cv_text="CV"))
    )

    errors = [e for e in events if e["type"] == "error"]
    assert "network error" in errors[0]["message"]
