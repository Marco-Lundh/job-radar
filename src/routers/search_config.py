from fastapi import APIRouter

import storage
from models import SearchConfig

router = APIRouter(tags=["Search config"])


@router.get("/search-config", response_model=SearchConfig)
def get_search_config() -> SearchConfig:
    """Return current search configuration including work type filter."""
    return storage.load_search_config()


@router.put("/search-config", response_model=SearchConfig)
def update_search_config(body: SearchConfig) -> SearchConfig:
    """Update search configuration."""
    storage.save_search_config(body)
    return body
