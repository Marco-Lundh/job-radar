"""
Tests for static file serving via main.py.

JavaScript behaviour (Alpine.js, HTMX) requires a real browser —
use Playwright for that layer.
"""


def test_index_served_with_200(client):
    assert client.get("/").status_code == 200


def test_index_content_type_is_html(client):
    assert "text/html" in client.get("/").headers["content-type"]


def test_index_contains_doctype(client):
    assert "<!DOCTYPE html>" in client.get("/").text


def test_index_contains_root_app_div(client):
    assert 'id="app"' in client.get("/").text


def test_index_loads_alpine_js(client):
    assert "alpinejs" in client.get("/").text


def test_index_loads_htmx(client):
    assert "htmx" in client.get("/").text


def test_style_css_served_with_200(client):
    assert client.get("/style.css").status_code == 200


def test_style_css_content_type(client):
    assert "text/css" in client.get("/style.css").headers["content-type"]
