from fastapi import APIRouter

import storage
from models import AppSettings

router = APIRouter(tags=["Settings"])


@router.get("/settings", response_model=AppSettings)
def get_settings() -> AppSettings:
    """Return current application settings."""
    return storage.load_app_settings()


@router.put("/settings", response_model=AppSettings)
def update_settings(body: AppSettings) -> AppSettings:
    """Update application settings."""
    storage.save_app_settings(body)
    return body
