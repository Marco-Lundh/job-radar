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


# --- GET /api/jobs ---


def test_list_jobs_empty(client):
    assert client.get("/api/jobs").json() == []


def test_list_jobs_returns_all(client):
    storage.save_jobs([_make_job(id="j1"), _make_job(id="j2")])
    assert len(client.get("/api/jobs").json()) == 2


def test_list_jobs_filter_by_status(client):
    storage.save_jobs(
        [
            _make_job(id="j1", status="new"),
            _make_job(id="j2", status="applied"),
        ]
    )
    data = client.get("/api/jobs?status=applied").json()
    assert len(data) == 1
    assert data[0]["id"] == "j2"


def test_list_jobs_filter_by_min_score(client):
    storage.save_jobs(
        [
            _make_job(id="j1", relevance_score=30),
            _make_job(id="j2", relevance_score=80),
        ]
    )
    data = client.get("/api/jobs?min_score=50").json()
    assert len(data) == 1
    assert data[0]["id"] == "j2"


def test_list_jobs_min_score_excludes_unranked(client):
    storage.save_jobs(
        [
            _make_job(id="j1"),
            _make_job(id="j2", relevance_score=70),
        ]
    )
    data = client.get("/api/jobs?min_score=50").json()
    assert len(data) == 1
    assert data[0]["id"] == "j2"


def test_list_jobs_filter_by_source(client):
    storage.save_jobs(
        [
            _make_job(id="j1", source="platsbanken"),
            _make_job(id="j2", source="adzuna"),
        ]
    )
    data = client.get("/api/jobs?source=adzuna").json()
    assert len(data) == 1
    assert data[0]["source"] == "adzuna"


def test_list_jobs_filter_by_work_type(client):
    storage.save_jobs(
        [
            _make_job(id="j1", work_type="remote"),
            _make_job(id="j2", work_type="on-site"),
        ]
    )
    data = client.get("/api/jobs?work_type=remote").json()
    assert len(data) == 1
    assert data[0]["work_type"] == "remote"


def test_list_jobs_filter_work_type_multi_value(client):
    storage.save_jobs(
        [
            _make_job(id="j1", work_type="remote"),
            _make_job(id="j2", work_type="hybrid"),
            _make_job(id="j3", work_type="on-site"),
        ]
    )
    data = client.get("/api/jobs?work_type=remote&work_type=hybrid").json()
    assert len(data) == 2
    assert {j["id"] for j in data} == {"j1", "j2"}


# --- GET /api/jobs/{job_id} ---


def test_get_job_returns_existing(client):
    storage.save_jobs([_make_job(id="abc")])
    r = client.get("/api/jobs/abc")
    assert r.status_code == 200
    assert r.json()["id"] == "abc"


def test_get_job_missing_returns_404(client):
    assert client.get("/api/jobs/doesnotexist").status_code == 404


# --- PATCH /api/jobs/{job_id} ---


def test_patch_job_status(client):
    storage.save_jobs([_make_job(id="j1")])
    r = client.patch("/api/jobs/j1", json={"status": "interesting"})
    assert r.status_code == 200
    assert r.json()["status"] == "interesting"


def test_patch_job_notes(client):
    storage.save_jobs([_make_job(id="j1")])
    r = client.patch("/api/jobs/j1", json={"notes": "Great company"})
    assert r.status_code == 200
    assert r.json()["notes"] == "Great company"


def test_patch_job_persists_change(client):
    storage.save_jobs([_make_job(id="j1")])
    client.patch("/api/jobs/j1", json={"status": "applied"})
    job = storage.get_job("j1")
    assert job is not None
    assert job.status == "applied"


def test_patch_job_missing_returns_404(client):
    assert (
        client.patch("/api/jobs/missing", json={"status": "new"}).status_code
        == 404
    )


# --- DELETE /api/jobs ---


def test_delete_jobs_without_confirm_returns_400(client):
    storage.save_jobs([_make_job()])
    assert client.delete("/api/jobs").status_code == 400


def test_delete_jobs_with_confirm_clears_all(client):
    storage.save_jobs([_make_job()])
    r = client.delete("/api/jobs?confirm=true")
    assert r.status_code == 200
    assert r.json()["deleted"] is True
    assert storage.load_jobs() == []
