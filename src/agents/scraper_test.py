import json

import storage
from agents.scraper import run_scraper_agent
from models import Job, SearchConfig, SourceConfig


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


def _mock_platsbanken(*jobs: Job) -> type:
    """Stub PlatsbankenSource that yields the given jobs."""

    class _MockSource:
        async def search(self, keywords, location, work_type, max_jobs):
            for job in jobs:
                yield job

    return _MockSource


def _config(**kwargs) -> SearchConfig:
    defaults = {
        "keywords": ["python"],
        "sources": [SourceConfig(name="platsbanken", enabled=True)],
    }
    return SearchConfig(**{**defaults, **kwargs})


# --- tests ---


async def test_scraper_stores_new_jobs(tmp_data, monkeypatch):
    monkeypatch.setattr(
        "agents.scraper.PlatsbankenSource",
        _mock_platsbanken(_make_job(id="new-1"), _make_job(id="new-2")),
    )

    events = await _collect(run_scraper_agent(_config()))

    assert events[-1]["type"] == "done"
    assert events[-1]["new_jobs"] == 2
    assert len(storage.load_jobs()) == 2


async def test_scraper_deduplicates_existing_jobs(tmp_data, monkeypatch):
    storage.save_jobs([_make_job(id="existing")])
    monkeypatch.setattr(
        "agents.scraper.PlatsbankenSource",
        _mock_platsbanken(_make_job(id="existing"), _make_job(id="truly-new")),
    )

    events = await _collect(run_scraper_agent(_config()))

    assert events[-1]["new_jobs"] == 1
    assert len(storage.load_jobs()) == 2


async def test_scraper_skips_disabled_source(tmp_data, monkeypatch):
    monkeypatch.setattr(
        "agents.scraper.PlatsbankenSource",
        _mock_platsbanken(_make_job(id="should-not-appear")),
    )
    config = _config(sources=[SourceConfig(name="platsbanken", enabled=False)])

    events = await _collect(run_scraper_agent(config))

    assert events[-1]["new_jobs"] == 0
    assert storage.load_jobs() == []


async def test_scraper_emits_error_for_unknown_source(tmp_data):
    config = _config(
        sources=[SourceConfig(name="unknown-source", enabled=True)]
    )

    events = await _collect(run_scraper_agent(config))

    error_events = [e for e in events if e["type"] == "error"]
    assert error_events
    assert "unknown-source" in error_events[0]["message"]


async def test_scraper_emits_error_when_source_raises(tmp_data, monkeypatch):
    class _FailingSource:
        async def search(self, **kwargs):
            raise RuntimeError("API unavailable")
            yield  # make it an async generator

    monkeypatch.setattr("agents.scraper.PlatsbankenSource", _FailingSource)

    events = await _collect(run_scraper_agent(_config()))

    error_events = [e for e in events if e["type"] == "error"]
    assert error_events
    assert "API unavailable" in error_events[0]["message"]


async def test_scraper_emits_progress_events(tmp_data, monkeypatch):
    monkeypatch.setattr(
        "agents.scraper.PlatsbankenSource",
        _mock_platsbanken(_make_job(id="j1")),
    )

    events = await _collect(run_scraper_agent(_config()))

    progress = [e for e in events if e["type"] == "progress"]
    assert progress


async def test_scraper_no_sources_emits_done(tmp_data):
    config = _config(sources=[])

    events = await _collect(run_scraper_agent(config))

    assert events[-1]["type"] == "done"
    assert events[-1]["new_jobs"] == 0
