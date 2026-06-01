# JobRadar — Specification

Multi-agent job search application. FastAPI backend with Pydantic AI agents,
simple HTML/HTMX/Alpine.js frontend. All state persisted locally as JSON.

---

## 1. Overview

The user defines a profile (desired role, location, skills, CV text/PDF).
Agents then scrape job listings from open APIs, filter them by relevance,
score individual jobs against the CV, and draft cover letters — all
independently triggerable from the UI with live progress updates.

---

## 2. Agents

Four agents, each independently triggerable from the UI.

### 2.1 ScraperAgent

Fetches raw job listings from configured sources and appends new jobs to
`data/jobs.json`. Deduplicates by job ID so re-runs are safe.

**Input**
```json
{
  "keywords": ["backend developer", "python"],
  "location": "Stockholm",
  "work_type": "hybrid",
  "sources": ["platsbanken"]
}
```

**Output** — streams SSE progress events, then writes to `data/jobs.json`.

**Behaviour**
- Paginates through API results until exhausted or a configurable `max_jobs`
  limit is reached.
- Each new job gets `status: "new"` and `scraped_at` timestamp.
- Already-known job IDs are skipped silently.
- The `work_type` filter is passed to the source API when supported; for
  sources that do not support it natively the agent post-filters results.
- Source is resolved via a `BaseJobSource` abstraction (see §6).

---

### 2.2 FilterAgent

Scores each unfiltered job against the user profile and writes a
`relevance_score` (0–100), `relevance_reason`, and detected `work_type` back
to `jobs.json`.

**Input** — profile from `data/profile.json`, jobs without a
`relevance_score`, and the configured `work_type` preference.

**Runs per job:** one Groq call per job, streamed progress in UI.

**Output per job**
```json
{
  "relevance_score": 72,
  "relevance_reason": "Matches Python + backend focus, but role is senior-level.",
  "work_type": "hybrid"
}
```

**Behaviour**
- Can be re-triggered on all unscored jobs, or on a single job.
- Work type is extracted from the job description as part of the same Groq
  call — no extra API cost. The LLM reads the full description and outputs
  one of `"remote"`, `"hybrid"`, `"on-site"`, or `"unknown"`. This handles
  any language and any phrasing variation.
- The configured `work_type` filter is included in the relevance prompt so
  the LLM can penalise mismatches (e.g. on-site job when user wants remote).
- Supports job descriptions in any language — the LLM responds in the
  application's configured UI language.

---

### 2.3 ScorerAgent

Produces a detailed CV-fit analysis for a single selected job. Mirrors the
logic from the `cv-fit-score` project.

**Input**
```json
{
  "job_id": "abc123",
  "cv_text": "..."   // from profile, or overridden per-call
}
```

**Output** — written to `jobs.json` under the job entry:
```json
{
  "fit_score": 78,
  "strengths": ["Strong Python background", "..."],
  "weaknesses": ["No Java mentioned", "..."],
  "recommendations": ["Highlight async experience", "..."],
  "fit_summary": "Good overall match. Main gap is...",
  "scored_at": "2026-05-27T14:00:00Z"
}
```

**Behaviour**
- Triggered on-demand per job from the job detail view.
- Can be re-run any number of times (overwrites previous score).
- Accepts both PDF upload (extracted via `pdfplumber`) (pdf default selected)
  and plain-text CV.

---

### 2.4 CoverLetterAgent

Generates a personalised cover letter for a selected job.

**Input**
```json
{
  "job_id": "abc123",
  "hints": "Emphasise team lead experience. Mention my interest in open source."
}
```

**Output**
- Plaintext cover letter, written to `data/cover_letters/{job_id}.txt`.
- Returned to the frontend for inline editing.

**Behaviour**
- Always triggered manually by the user from the Job Detail panel.
- Every edit in the UI auto-saves back to the same file (debounced, 1 s).
- Manual "Save" button also available.
- Export buttons: download as `.txt` or `.pdf` (generated server-side via
  `fpdf2`).
- Re-generating overwrites the file and resets the editor.
- Language follows the job's detected language (extracted by FilterAgent),
  not the UI language.

---

## 3. Data Models

### 3.1 Job

```python
class Job(BaseModel):
    id: str                        # from source API or generated UUID
    source: str                    # "platsbanken"
    title: str
    company: str
    location: str
    work_type: Literal[
        "remote", "hybrid", "on-site", "unknown"
    ] = "unknown"
    description: str
    url: str
    posted_date: str | None
    scraped_at: str                # ISO 8601

    # FilterAgent
    relevance_score: int | None = None
    relevance_reason: str | None = None
    filtered_at: str | None = None

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
```

### 3.2 Profile

```python
class Profile(BaseModel):
    desired_title: str             # e.g. "Backend Developer"
    location: str                  # e.g. "Stockholm"
    skills: list[str]              # e.g. ["Python", "FastAPI", "Docker"]
    experience_years: int
    languages: list[str]           # e.g. ["Swedish", "English"]
    summary: str                   # free-text self-description for agents
    cv_text: str | None = None
    cv_pdf_filename: str | None = None
```

### 3.3 SearchConfig

```python
class SourceConfig(BaseModel):
    name: str                      # "platsbanken"
    enabled: bool = True

class SearchConfig(BaseModel):
    keywords: list[str]
    location: str | None = None
    work_type: list[Literal["remote", "hybrid", "on-site"]] = [
        "remote", "hybrid", "on-site"
    ]                              # empty list = no filter
    max_jobs: int = 100
    sources: list[SourceConfig]
```

### 3.4 AppSettings

Persisted to `data/settings.json`. Controls UI and agent behaviour
application-wide.

```python
class AppSettings(BaseModel):
    ui_language: str = "en"        # BCP-47 language tag, e.g. "en", "sv", "de"
```

The UI language is loaded on app start and applied to all frontend labels and
agent prompts. When the user changes the language in Settings, the new value is
saved immediately and becomes the default for all subsequent sessions.

---

## 4. Storage Layout

```
data/
  profile.json          ← Profile model
  jobs.json             ← list[Job]
  search_config.json    ← SearchConfig
  settings.json         ← AppSettings
  cover_letters/
    {job_id}.txt        ← one file per job, updated on every save
```

All reads and writes go through a thin `storage.py` module with typed
helpers (`load_jobs`, `save_jobs`, `load_profile`, `load_settings`,
`save_settings`, etc.).

No database — plain JSON. Loading all jobs into memory is acceptable given
expected volume (hundreds, not millions).

---

## 5. API Endpoints

FastAPI exposes Swagger UI at `/docs` and ReDoc at `/redoc`. Every endpoint is
fully documented with request/response schemas so all agents and the UI can be
driven directly from the Swagger interface.

### Settings

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/settings` | Return current app settings (language, etc.) |
| `PUT` | `/api/settings` | Update app settings; persists new language as default |

### Profile

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/profile` | Return current profile |
| `PUT` | `/api/profile` | Update profile |
| `POST` | `/api/profile/cv/upload` | Upload CV as PDF; extracts text and updates profile |

### Search config

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/search-config` | Return current config (includes work_type) |
| `PUT` | `/api/search-config` | Update config (set work_type before scraping) |

### Agents (SSE streaming)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/agents/scrape` | Run ScraperAgent; SSE stream of progress |
| `POST` | `/api/agents/filter` | Run FilterAgent on all unscored jobs (also detects work type per job) |
| `POST` | `/api/agents/filter/{job_id}` | Re-filter a single job |
| `POST` | `/api/agents/score/{job_id}` | Run ScorerAgent on one job |
| `POST` | `/api/agents/cover-letter/{job_id}` | Run CoverLetterAgent for a specific job; body: `{ hints }` |

All SSE streams emit newline-delimited JSON events:
```
data: {"type": "progress", "message": "Found 12 jobs on Platsbanken..."}\n\n
data: {"type": "done", "job_id": "abc123"}\n\n
data: {"type": "error", "message": "..."}\n\n
```

### Jobs

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/jobs` | List jobs. Query: `status`, `min_score`, `source`, `work_type` (repeatable, e.g. `?work_type=remote&work_type=hybrid`) |
| `GET` | `/api/jobs/{job_id}` | Single job detail |
| `PATCH` | `/api/jobs/{job_id}` | Update `status` or `notes` |
| `DELETE` | `/api/jobs` | Clear all jobs (with confirmation flag) |

### Cover letters

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/cover-letters/{job_id}` | Return cover letter text |
| `PUT` | `/api/cover-letters/{job_id}` | Save edited text |
| `GET` | `/api/cover-letters/{job_id}/export/txt` | Download as `.txt` |
| `GET` | `/api/cover-letters/{job_id}/export/pdf` | Download as `.pdf` |

### Sources

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/sources` | List available source names |

### Frontend

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Serve `static/index.html` |

---

## 6. Job Source Abstraction

Adding a new source means creating one file in `src/sources/`.

```python
# sources/base.py
class BaseJobSource(ABC):
    name: str

    @abstractmethod
    async def search(
        self,
        keywords: list[str],
        location: str | None,
        work_type: str,
        max_jobs: int,
    ) -> AsyncIterator[Job]:
        ...
```

`PlatsbankenSource` implements this against the JobTech open API
(`https://jobsearch.api.jobtechdev.se/search`). No authentication required.

Future sources implement the same interface — no changes needed to agents or
routers.

---

## 7. Frontend

Single HTML page served by FastAPI. No build step.

**Libraries (loaded from CDN):**
- HTMX 2.x — reactive server-driven updates, SSE extension
- Alpine.js 3.x — local UI state (tabs, modals, form state)
- Simple custom CSS — no framework, design guidelines from global CLAUDE.md

### Internationalisation

All UI strings are stored in a JavaScript translation map keyed by BCP-47
language tag. On page load the frontend calls `GET /api/settings` to read
`ui_language` and applies the correct string set. Changing the language in the
Settings tab calls `PUT /api/settings` and reloads the page.

The initial supported languages are **English (`en`)** and **Swedish (`sv`)**,
but the translation map is designed so any language can be added by providing a
new key in the map.

### Sections (tab-based layout)

#### Settings tab
- Language selector dropdown (any supported language; persists on change).
- Changes take effect immediately on save — no restart required.

#### Profile tab
- Fields: desired title, location, skills (tag input), experience years,
  languages, summary textarea.
- CV input: paste plain text **or** upload PDF (mutually exclusive toggle).
- Auto-saves to `/api/profile` on blur/change.

#### Search tab
- Keyword list (add/remove tags).
- Location field.
- **Work type checkboxes** — Remote / Hybrid / On-site (multi-select;
  all checked by default = no filter). Value is saved to
  `SearchConfig.work_type` before agents start.
- Source checkboxes (one per available source).
- Max jobs slider.
- **"Start search"** button → POST to `/api/agents/scrape`, opens SSE
  progress panel below. Disabled until at least one keyword has been
  added; an inline validation message explains what is missing.

#### Jobs tab
- Table/card list of all jobs.
- Filter bar: status dropdown, minimum relevance score slider, source filter,
  work type checkboxes (multi-select).
- **"Filter all"** button → runs FilterAgent on unscored jobs, live progress
  inline.
- Each row: title, company, location, work type badge, relevance badge, fit
  badge, status dropdown, "Open" button.
- Clicking a job opens the Job Detail panel (right-side drawer or modal).

#### Job Detail panel
- Full job description.
- Work type badge (remote / hybrid / on-site / unknown).
- Relevance score + reason (if run).
- Fit score breakdown: strengths, weaknesses, recommendations (if run).
- Buttons: **"Score against CV"**, **"Generate cover letter"** (opens hints
  modal) — the generate button is always available regardless of rank.
- Cover letter status indicator: shows "Generated" or "Not generated".
- Notes textarea (auto-saved).
- Status selector.

#### Cover Letter panel
- Opens after CoverLetterAgent completes, or when clicking into a job with
  an existing letter.
- Contenteditable textarea with the letter text.
- Auto-saves on keystroke (debounced 1 s) via `PUT /api/cover-letters/{id}`.
- **"Export PDF"** and **"Export TXT"** download buttons.
- **"Regenerate"** button (shows hints input before re-running agent).

---

## 8. Tech Stack

| Layer | Technology |
|-------|-----------|
| Package manager | UV (project managed with `uv init`) |
| Web framework | FastAPI |
| API docs | Swagger UI (`/docs`) + ReDoc (`/redoc`) via FastAPI built-in |
| AI agents | Pydantic AI |
| LLM | Groq — `llama-3.3-70b-versatile` |
| PDF parsing (CV) | pdfplumber |
| PDF export (cover letter) | fpdf2 |
| HTTP client (job APIs) | httpx |
| Frontend reactivity | HTMX 2 + Alpine.js 3 |
| Data persistence | JSON files |
| Python version | 3.14.* |

---

## 9. Configuration (`.env`)

```dotenv
# LLM
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama-3.3-70b-versatile

# App
DATA_DIR=./data
MAX_JOBS_DEFAULT=100
HOST=127.0.0.1
PORT=8000
```

All settings loaded via a `Settings` class (Pydantic `BaseSettings`) in
`config.py`. `.env.example` is committed; `.env` is gitignored.

---

## 10. Project Structure

```
job-radar/
├── pyproject.toml           ← UV-managed; requires-python = ">=3.14"
├── uv.lock
├── uv.toml                  ← native-tls = true
├── .python-version          ← pins 3.14
├── .env.example
├── .env                     ← gitignored
├── .gitignore
├── data/                    ← gitignored
│   ├── profile.json
│   ├── jobs.json
│   ├── search_config.json
│   ├── settings.json
│   └── cover_letters/
├── static/
│   ├── index.html
│   └── style.css
└── src/
    ├── __init__.py
    ├── main.py          ← FastAPI app, mounts static, includes routers
    ├── config.py        ← Settings (Pydantic BaseSettings)
    ├── models.py        ← Job, Profile, SearchConfig, AppSettings
    ├── storage.py       ← load/save helpers for all JSON files
    ├── agents/
    │   ├── __init__.py
    │   ├── scraper.py
    │   ├── filter.py
    │   ├── scorer.py
    │   └── cover_letter.py
    ├── sources/
    │   ├── __init__.py
    │   ├── base.py      ← BaseJobSource ABC
    │   └── platsbanken.py
    └── routers/
        ├── __init__.py
        ├── settings.py
        ├── profile.py
        ├── search_config.py
        ├── jobs.py
        ├── agents.py
        └── cover_letters.py
```

---

## 11. Development Workflow

```bash
# Create project (first time)
uv init job-radar
cd job-radar

# Install deps
uv sync

# Run dev server
uv run fastapi dev src/main.py

# Run tests
uv run pytest src/ -v

# Open Swagger UI
open http://127.0.0.1:8000/docs
```

---

## 12. Out of Scope (v1)

- Browser automation / scraping behind login walls (LinkedIn, etc.)
- User authentication / multi-user support
- Remote deployment / Docker
- Email notifications
- Automatic scheduling of agents
- Job application tracking beyond the `status` field
