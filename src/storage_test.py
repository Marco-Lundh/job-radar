import pytest

import storage
from models import AppSettings, Job, Profile, SearchConfig


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


# --- load / save jobs ---


def test_load_jobs_empty_when_no_file(tmp_data):
    assert storage.load_jobs() == []


def test_save_and_load_jobs_roundtrip(tmp_data):
    storage.save_jobs([_make_job(id="j1"), _make_job(id="j2")])
    loaded = storage.load_jobs()
    assert len(loaded) == 2
    assert loaded[0].id == "j1"
    assert loaded[1].id == "j2"


def test_save_jobs_creates_parent_dirs(tmp_path, monkeypatch):
    from config import settings as app_settings

    nested = tmp_path / "nested" / "subdir"
    monkeypatch.setattr(app_settings, "data_dir", nested)
    storage.save_jobs([_make_job()])
    assert (nested / "jobs.json").exists()


def test_save_jobs_preserves_all_fields(tmp_data):
    job = _make_job(
        status="applied", notes="Great company", relevance_score=75
    )
    storage.save_jobs([job])
    loaded = storage.load_jobs()[0]
    assert loaded.status == "applied"
    assert loaded.notes == "Great company"
    assert loaded.relevance_score == 75


# --- get_job ---


def test_get_job_returns_existing(tmp_data):
    storage.save_jobs([_make_job(id="abc")])
    job = storage.get_job("abc")
    assert job is not None
    assert job.id == "abc"


def test_get_job_returns_none_for_missing(tmp_data):
    storage.save_jobs([])
    assert storage.get_job("missing") is None


def test_get_job_returns_none_from_empty_store(tmp_data):
    assert storage.get_job("x") is None


# --- upsert_job ---


def test_upsert_job_inserts_new(tmp_data):
    storage.upsert_job(_make_job(id="x"))
    assert len(storage.load_jobs()) == 1


def test_upsert_job_updates_existing(tmp_data):
    storage.upsert_job(_make_job(id="x", status="new"))
    storage.upsert_job(_make_job(id="x", status="applied"))
    jobs = storage.load_jobs()
    assert len(jobs) == 1
    assert jobs[0].status == "applied"


def test_upsert_job_multiple_inserts(tmp_data):
    for i in range(3):
        storage.upsert_job(_make_job(id=f"job-{i}"))
    assert len(storage.load_jobs()) == 3


# --- batch_upsert_jobs ---


def test_batch_upsert_updates_multiple_jobs(tmp_data):
    storage.save_jobs([_make_job(id="a"), _make_job(id="b")])
    storage.batch_upsert_jobs(
        [
            _make_job(id="a", status="interesting"),
            _make_job(id="b", status="dismissed"),
        ]
    )
    jobs = {j.id: j for j in storage.load_jobs()}
    assert jobs["a"].status == "interesting"
    assert jobs["b"].status == "dismissed"


def test_batch_upsert_inserts_new_jobs(tmp_data):
    storage.batch_upsert_jobs([_make_job(id="n1"), _make_job(id="n2")])
    assert len(storage.load_jobs()) == 2


def test_batch_upsert_mixes_update_and_insert(tmp_data):
    storage.save_jobs([_make_job(id="existing")])
    storage.batch_upsert_jobs(
        [
            _make_job(id="existing", status="applied"),
            _make_job(id="new"),
        ]
    )
    jobs = {j.id: j for j in storage.load_jobs()}
    assert len(jobs) == 2
    assert jobs["existing"].status == "applied"


# --- profile ---


def test_load_profile_returns_defaults_when_missing(tmp_data):
    profile = storage.load_profile()
    assert isinstance(profile, Profile)
    assert profile.desired_title == ""


def test_save_and_load_profile_roundtrip(tmp_data):
    p = Profile(
        desired_title="Backend Dev", location="Stockholm", experience_years=5
    )
    storage.save_profile(p)
    loaded = storage.load_profile()
    assert loaded.desired_title == "Backend Dev"
    assert loaded.location == "Stockholm"
    assert loaded.experience_years == 5


def test_save_profile_preserves_skills_list(tmp_data):
    storage.save_profile(Profile(skills=["Python", "FastAPI", "Docker"]))
    assert storage.load_profile().skills == ["Python", "FastAPI", "Docker"]


# --- search config ---


def test_load_search_config_returns_defaults_when_missing(tmp_data):
    assert isinstance(storage.load_search_config(), SearchConfig)


def test_save_and_load_search_config_roundtrip(tmp_data):
    storage.save_search_config(
        SearchConfig(keywords=["python", "fastapi"], max_jobs=50)
    )
    loaded = storage.load_search_config()
    assert loaded.keywords == ["python", "fastapi"]
    assert loaded.max_jobs == 50


def test_save_search_config_preserves_work_type(tmp_data):
    storage.save_search_config(SearchConfig(work_type=["remote"]))
    assert storage.load_search_config().work_type == ["remote"]


# --- app settings ---


def test_load_app_settings_returns_defaults_when_missing(tmp_data):
    s = storage.load_app_settings()
    assert isinstance(s, AppSettings)
    assert s.ui_language == "en"


def test_save_and_load_app_settings_roundtrip(tmp_data):
    storage.save_app_settings(AppSettings(ui_language="sv"))
    assert storage.load_app_settings().ui_language == "sv"


# --- cover letters ---


def test_load_cover_letter_returns_none_when_missing(tmp_data):
    assert storage.load_cover_letter("job-1") is None


def test_save_and_load_cover_letter_roundtrip(tmp_data):
    storage.save_cover_letter("job-1", "Dear Hiring Manager...")
    assert storage.load_cover_letter("job-1") == "Dear Hiring Manager..."


def test_cover_letter_exists_false_initially(tmp_data):
    assert not storage.cover_letter_exists("job-1")


def test_cover_letter_exists_true_after_save(tmp_data):
    storage.save_cover_letter("job-1", "Text")
    assert storage.cover_letter_exists("job-1")


def test_save_cover_letter_overwrites_existing(tmp_data):
    storage.save_cover_letter("job-1", "Version 1")
    storage.save_cover_letter("job-1", "Version 2")
    assert storage.load_cover_letter("job-1") == "Version 2"


def test_load_cover_letter_raises_on_path_traversal(tmp_data):
    with pytest.raises(ValueError):
        storage.load_cover_letter("../../../etc/passwd")


def test_save_cover_letter_raises_on_path_traversal(tmp_data):
    with pytest.raises(ValueError):
        storage.save_cover_letter("job/../../secret", "text")


def test_save_cover_letter_preserves_unicode(tmp_data):
    text = "Kära rekryterare, tack för möjligheten."
    storage.save_cover_letter("job-1", text)
    assert storage.load_cover_letter("job-1") == text
