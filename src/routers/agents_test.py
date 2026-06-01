import storage
from models import Job


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


async def _done_stream(*_args, **_kwargs):
    yield 'data: {"type": "done"}\n\n'


# --- POST /api/agents/scrape ---


def test_scrape_returns_event_stream(client, monkeypatch):
    monkeypatch.setattr("routers.agents.run_scraper_agent", _done_stream)
    r = client.post("/api/agents/scrape")
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]


def test_scrape_response_contains_sse_event(client, monkeypatch):
    monkeypatch.setattr("routers.agents.run_scraper_agent", _done_stream)
    assert "done" in client.post("/api/agents/scrape").text


def test_scrape_passes_search_config_to_agent(client, monkeypatch):
    from models import SearchConfig

    storage.save_search_config(SearchConfig(keywords=["python"]))
    received: list = []

    async def _capture(config, *args, **kwargs):
        received.append(config)
        yield 'data: {"type": "done"}\n\n'

    monkeypatch.setattr("routers.agents.run_scraper_agent", _capture)
    client.post("/api/agents/scrape")
    assert received[0].keywords == ["python"]


# --- POST /api/agents/rank ---


def test_rank_all_returns_event_stream(client, monkeypatch):
    monkeypatch.setattr("routers.agents.run_ranker_agent", _done_stream)
    r = client.post("/api/agents/rank")
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]


def test_rank_all_response_contains_sse_event(client, monkeypatch):
    monkeypatch.setattr("routers.agents.run_ranker_agent", _done_stream)
    assert "done" in client.post("/api/agents/rank").text


# --- POST /api/agents/rank/{job_id} ---


def test_rank_single_returns_event_stream(client, monkeypatch):
    monkeypatch.setattr("routers.agents.run_ranker_agent", _done_stream)
    r = client.post("/api/agents/rank/job-1")
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]


def test_rank_single_passes_job_id_to_agent(client, monkeypatch):
    received: list = []

    async def _capture(*args, job_id=None, **kwargs):
        received.append(job_id)
        yield 'data: {"type": "done"}\n\n'

    monkeypatch.setattr("routers.agents.run_ranker_agent", _capture)
    client.post("/api/agents/rank/my-job-id")
    assert received[0] == "my-job-id"


# --- POST /api/agents/score/{job_id} ---


def test_score_returns_event_stream(client, monkeypatch):
    monkeypatch.setattr("routers.agents.run_scorer_agent", _done_stream)
    r = client.post("/api/agents/score/job-1")
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]


def test_score_passes_job_id_to_agent(client, monkeypatch):
    received: list = []

    async def _capture(job_id, *args, **kwargs):
        received.append(job_id)
        yield 'data: {"type": "done"}\n\n'

    monkeypatch.setattr("routers.agents.run_scorer_agent", _capture)
    client.post("/api/agents/score/target-job")
    assert received[0] == "target-job"


# --- POST /api/agents/cover-letter/{job_id} ---


def test_cover_letter_returns_event_stream(client, monkeypatch):
    monkeypatch.setattr("routers.agents.run_cover_letter_agent", _done_stream)
    r = client.post("/api/agents/cover-letter/job-1", json={"hints": ""})
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]


def test_cover_letter_passes_hints_to_agent(client, monkeypatch):
    received: list = []

    async def _capture(job_id, profile, hints="", **kwargs):
        received.append(hints)
        yield 'data: {"type": "done"}\n\n'

    monkeypatch.setattr("routers.agents.run_cover_letter_agent", _capture)
    client.post(
        "/api/agents/cover-letter/job-1",
        json={"hints": "Emphasize leadership"},
    )
    assert received[0] == "Emphasize leadership"
