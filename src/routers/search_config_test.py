import storage
from models import SearchConfig


# --- GET /api/search-config ---


def test_get_search_config_returns_defaults(client):
    r = client.get("/api/search-config")
    assert r.status_code == 200
    data = r.json()
    assert "keywords" in data
    assert "work_type" in data
    assert "max_jobs" in data


def test_get_search_config_returns_saved(client):
    storage.save_search_config(SearchConfig(keywords=["python"], max_jobs=25))
    data = client.get("/api/search-config").json()
    assert data["keywords"] == ["python"]
    assert data["max_jobs"] == 25


# --- PUT /api/search-config ---


def test_update_search_config_keywords(client):
    payload = {
        "keywords": ["python", "fastapi"],
        "location": "Stockholm",
        "work_type": ["remote"],
        "max_jobs": 50,
        "sources": [{"name": "platsbanken", "enabled": True}],
    }
    r = client.put("/api/search-config", json=payload)
    assert r.status_code == 200
    assert r.json()["keywords"] == ["python", "fastapi"]


def test_update_search_config_is_persisted(client):
    client.put(
        "/api/search-config",
        json={
            "keywords": ["django"],
            "location": None,
            "work_type": ["hybrid", "on-site"],
            "max_jobs": 10,
            "sources": [{"name": "platsbanken", "enabled": True}],
        },
    )
    loaded = storage.load_search_config()
    assert loaded.keywords == ["django"]
    assert loaded.max_jobs == 10


def test_update_search_config_work_type_persisted(client):
    client.put(
        "/api/search-config",
        json={
            "keywords": [],
            "location": None,
            "work_type": ["remote"],
            "max_jobs": 100,
            "sources": [],
        },
    )
    assert storage.load_search_config().work_type == ["remote"]
