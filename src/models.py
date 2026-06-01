from typing import Literal

from pydantic import BaseModel


class Job(BaseModel):
    id: str
    source: str
    title: str
    company: str
    location: str
    work_type: Literal["remote", "hybrid", "on-site", "unknown"] = "unknown"
    description: str
    url: str
    posted_date: str | None = None
    scraped_at: str

    # RankerAgent
    relevance_score: int | None = None
    relevance_reason: str | None = None
    ranked_at: str | None = None

    # ScorerAgent
    fit_score: int | None = None
    strengths: list[str] = []
    weaknesses: list[str] = []
    recommendations: list[str] = []
    fit_summary: str | None = None
    scored_at: str | None = None

    # User state
    status: Literal["new", "interesting", "applied", "dismissed"] = "new"
    notes: str = ""


class Profile(BaseModel):
    desired_title: str = ""
    location: str = ""
    skills: list[str] = []
    experience_years: int = 0
    languages: list[str] = []
    summary: str = ""
    cv_text: str | None = None
    cv_pdf_filename: str | None = None


class SourceConfig(BaseModel):
    name: str
    enabled: bool = True


class SearchConfig(BaseModel):
    keywords: list[str] = []
    location: str | None = None
    work_type: list[Literal["remote", "hybrid", "on-site"]] = [
        "remote",
        "hybrid",
        "on-site",
    ]
    max_jobs: int = 100
    sources: list[SourceConfig] = [SourceConfig(name="platsbanken")]


class AppSettings(BaseModel):
    ui_language: str = "en"


# --- Request/response bodies ---


class JobPatch(BaseModel):
    status: Literal["new", "interesting", "applied", "dismissed"] | None = None
    notes: str | None = None


class CoverLetterSaveRequest(BaseModel):
    text: str


class CoverLetterGenerateRequest(BaseModel):
    hints: str = ""


class RankerOutput(BaseModel):
    relevance_score: int
    relevance_reason: str
    work_type: Literal["remote", "hybrid", "on-site", "unknown"]


class ScoreOutput(BaseModel):
    fit_score: int
    strengths: list[str]
    weaknesses: list[str]
    recommendations: list[str]
    fit_summary: str
