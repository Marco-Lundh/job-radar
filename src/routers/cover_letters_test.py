import storage


# --- GET /api/cover-letters/{job_id} ---


def test_get_cover_letter_missing_returns_404(client):
    assert client.get("/api/cover-letters/job-1").status_code == 404


def test_get_cover_letter_returns_text(client):
    storage.save_cover_letter("job-1", "Dear Hiring Manager...")
    r = client.get("/api/cover-letters/job-1")
    assert r.status_code == 200
    assert r.json()["text"] == "Dear Hiring Manager..."
    assert r.json()["job_id"] == "job-1"


# --- PUT /api/cover-letters/{job_id} ---


def test_save_cover_letter_returns_success(client):
    r = client.put("/api/cover-letters/job-1", json={"text": "My letter"})
    assert r.status_code == 200
    assert r.json()["saved"] is True


def test_save_cover_letter_persists_text(client):
    client.put("/api/cover-letters/job-1", json={"text": "Persistent letter"})
    assert storage.load_cover_letter("job-1") == "Persistent letter"


def test_save_cover_letter_overwrites_existing(client):
    client.put("/api/cover-letters/job-1", json={"text": "Version 1"})
    client.put("/api/cover-letters/job-1", json={"text": "Version 2"})
    assert storage.load_cover_letter("job-1") == "Version 2"


# --- GET /api/cover-letters/{job_id}/export/txt ---


def test_export_txt_missing_returns_404(client):
    assert client.get("/api/cover-letters/job-1/export/txt").status_code == 404


def test_export_txt_returns_text_content(client):
    storage.save_cover_letter("job-1", "Letter text here")
    r = client.get("/api/cover-letters/job-1/export/txt")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    assert r.text == "Letter text here"


def test_export_txt_content_disposition_header(client):
    storage.save_cover_letter("job-1", "text")
    r = client.get("/api/cover-letters/job-1/export/txt")
    assert "attachment" in r.headers["content-disposition"]
    assert "job-1" in r.headers["content-disposition"]


# --- GET /api/cover-letters/{job_id}/export/pdf ---


def test_export_pdf_missing_returns_404(client):
    assert client.get("/api/cover-letters/job-1/export/pdf").status_code == 404


def test_export_pdf_content_type(client):
    storage.save_cover_letter("job-1", "Letter text")
    r = client.get("/api/cover-letters/job-1/export/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"


def test_export_pdf_is_valid_pdf(client):
    storage.save_cover_letter("job-1", "Letter text")
    r = client.get("/api/cover-letters/job-1/export/pdf")
    assert r.content.startswith(b"%PDF")


def test_export_pdf_content_disposition_header(client):
    storage.save_cover_letter("job-1", "text")
    r = client.get("/api/cover-letters/job-1/export/pdf")
    assert "attachment" in r.headers["content-disposition"]
    assert "job-1" in r.headers["content-disposition"]
