import json
import re
from pathlib import Path
from typing import Any

from config import settings as app_settings
from models import AppSettings, Job, Profile, SearchConfig


def _read(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# --- Jobs ---


def load_jobs() -> list[Job]:
    raw = _read(app_settings.data_dir / "jobs.json", [])
    return [Job.model_validate(j) for j in raw]


def save_jobs(jobs: list[Job]) -> None:
    _write(
        app_settings.data_dir / "jobs.json",
        [j.model_dump() for j in jobs],
    )


def get_job(job_id: str) -> Job | None:
    return next((j for j in load_jobs() if j.id == job_id), None)


def upsert_job(job: Job) -> None:
    jobs = load_jobs()
    for i, j in enumerate(jobs):
        if j.id == job.id:
            jobs[i] = job
            save_jobs(jobs)
            return
    jobs.append(job)
    save_jobs(jobs)


# --- Profile ---


def load_profile() -> Profile:
    return Profile.model_validate(
        _read(app_settings.data_dir / "profile.json", {})
    )


def save_profile(profile: Profile) -> None:
    _write(
        app_settings.data_dir / "profile.json",
        profile.model_dump(),
    )


# --- SearchConfig ---


def load_search_config() -> SearchConfig:
    return SearchConfig.model_validate(
        _read(app_settings.data_dir / "search_config.json", {})
    )


def save_search_config(config: SearchConfig) -> None:
    _write(
        app_settings.data_dir / "search_config.json",
        config.model_dump(),
    )


# --- AppSettings ---


def load_app_settings() -> AppSettings:
    return AppSettings.model_validate(
        _read(app_settings.data_dir / "settings.json", {})
    )


def save_app_settings(s: AppSettings) -> None:
    _write(app_settings.data_dir / "settings.json", s.model_dump())


# --- Cover letters ---


_JOB_ID_RE = re.compile(r"[A-Za-z0-9_-]+")


def _cover_letter_path(job_id: str) -> Path:
    if not _JOB_ID_RE.fullmatch(job_id):
        raise ValueError(f"Invalid job_id: {job_id!r}")
    base = app_settings.cover_letters_dir.resolve()
    path = (base / f"{job_id}.txt").resolve()
    if not path.is_relative_to(base):
        raise ValueError(f"Invalid job_id: {job_id!r}")
    return path


def load_cover_letter(job_id: str) -> str | None:
    path = _cover_letter_path(job_id)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def save_cover_letter(job_id: str, text: str) -> None:
    path = _cover_letter_path(job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def cover_letter_exists(job_id: str) -> bool:
    return _cover_letter_path(job_id).exists()


def batch_upsert_jobs(updated: list[Job]) -> None:
    """Update multiple jobs in a single read/write cycle."""
    all_jobs = load_jobs()
    by_id = {j.id: j for j in all_jobs}
    for job in updated:
        by_id[job.id] = job
    save_jobs(list(by_id.values()))
