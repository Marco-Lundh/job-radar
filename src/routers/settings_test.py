import storage
from models import AppSettings


# --- GET /api/settings ---


def test_get_settings_returns_default_language(client):
    r = client.get("/api/settings")
    assert r.status_code == 200
    assert r.json()["ui_language"] == "en"


def test_get_settings_returns_saved_language(client):
    storage.save_app_settings(AppSettings(ui_language="sv"))
    assert client.get("/api/settings").json()["ui_language"] == "sv"


# --- PUT /api/settings ---


def test_update_settings_language(client):
    r = client.put("/api/settings", json={"ui_language": "de"})
    assert r.status_code == 200
    assert r.json()["ui_language"] == "de"


def test_update_settings_is_persisted(client):
    client.put("/api/settings", json={"ui_language": "fr"})
    assert storage.load_app_settings().ui_language == "fr"
