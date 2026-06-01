import storage
from models import Profile


def _make_minimal_pdf() -> bytes:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, "Test CV content")
    return bytes(pdf.output())


# --- GET /api/profile ---


def test_get_profile_returns_defaults(client):
    r = client.get("/api/profile")
    assert r.status_code == 200
    assert r.json()["desired_title"] == ""


def test_get_profile_returns_saved_profile(client):
    storage.save_profile(Profile(desired_title="Backend Dev"))
    assert client.get("/api/profile").json()["desired_title"] == "Backend Dev"


# --- PUT /api/profile ---


def test_update_profile_and_retrieve(client):
    payload = {
        "desired_title": "Backend Dev",
        "location": "Stockholm",
        "skills": ["Python", "FastAPI"],
        "experience_years": 5,
        "languages": ["Swedish", "English"],
        "summary": "Experienced developer",
    }
    r = client.put("/api/profile", json=payload)
    assert r.status_code == 200
    assert r.json()["desired_title"] == "Backend Dev"


def test_update_profile_is_persisted(client):
    client.put(
        "/api/profile",
        json={
            "desired_title": "ML Engineer",
            "location": "",
            "skills": ["Python"],
            "experience_years": 3,
            "languages": [],
            "summary": "",
        },
    )
    assert storage.load_profile().desired_title == "ML Engineer"


def test_update_profile_skills_round_trip(client):
    r = client.put(
        "/api/profile",
        json={
            "desired_title": "",
            "location": "",
            "skills": ["Rust", "Go", "C++"],
            "experience_years": 0,
            "languages": [],
            "summary": "",
        },
    )
    assert r.json()["skills"] == ["Rust", "Go", "C++"]


# --- POST /api/profile/cv/upload ---


def test_upload_cv_non_pdf_rejected(client):
    r = client.post(
        "/api/profile/cv/upload",
        files={"file": ("cv.txt", b"not a pdf", "text/plain")},
    )
    assert r.status_code == 400


def test_upload_cv_valid_pdf_accepted(client):
    r = client.post(
        "/api/profile/cv/upload",
        files={"file": ("my_cv.pdf", _make_minimal_pdf(), "application/pdf")},
    )
    assert r.status_code == 200
    assert r.json()["cv_pdf_filename"] == "my_cv.pdf"


def test_upload_cv_extracts_text(client):
    r = client.post(
        "/api/profile/cv/upload",
        files={"file": ("my_cv.pdf", _make_minimal_pdf(), "application/pdf")},
    )
    assert "Test CV content" in (r.json()["cv_text"] or "")
