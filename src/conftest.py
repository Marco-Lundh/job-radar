import os

# Must happen before any src import — Settings() validates GROQ_API_KEY
# at construction time.
os.environ.setdefault("GROQ_API_KEY", "test-key-for-tests")

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def tmp_data(tmp_path, monkeypatch):
    """Redirect all storage I/O to a temporary directory."""
    from config import settings as app_settings

    monkeypatch.setattr(app_settings, "data_dir", tmp_path)
    return tmp_path


@pytest.fixture()
def client(tmp_data):
    from main import app

    return TestClient(app)
