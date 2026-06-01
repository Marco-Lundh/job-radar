import io

import pdfplumber
from fastapi import APIRouter, HTTPException, UploadFile

import storage
from models import Profile

router = APIRouter(tags=["Profile"])


@router.get("/profile", response_model=Profile)
def get_profile() -> Profile:
    """Return the current user profile."""
    return storage.load_profile()


@router.put("/profile", response_model=Profile)
def update_profile(body: Profile) -> Profile:
    """Update the user profile."""
    storage.save_profile(body)
    return body


@router.post("/profile/cv/upload", response_model=Profile)
async def upload_cv(file: UploadFile) -> Profile:
    """Upload a PDF CV; extracts text and saves it to the profile."""
    contents = await file.read()
    if not contents.startswith(b"%PDF"):
        raise HTTPException(
            status_code=400, detail="Only PDF files are accepted."
        )
    with pdfplumber.open(io.BytesIO(contents)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    profile = storage.load_profile()
    profile.cv_text = text
    profile.cv_pdf_filename = file.filename
    storage.save_profile(profile)
    return profile
