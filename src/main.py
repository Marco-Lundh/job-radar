from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from routers import (
    agents,
    cover_letters,
    jobs,
    profile,
    search_config,
    settings,
)

app = FastAPI(
    title="JobRadar",
    description=(
        "AI-powered job search that tells you which listings actually matter."
    ),
    version="0.1.0",
)

app.include_router(settings.router, prefix="/api")
app.include_router(profile.router, prefix="/api")
app.include_router(search_config.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(agents.router, prefix="/api")
app.include_router(cover_letters.router, prefix="/api")

static_dir = Path(__file__).parent.parent / "static"
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
