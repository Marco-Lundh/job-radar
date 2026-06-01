import io
import os
import pathlib
import sys

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse
from fpdf import FPDF

import storage
from models import CoverLetterSaveRequest

router = APIRouter(prefix="/cover-letters", tags=["Cover letters"])


@router.get("/{job_id}")
def get_cover_letter(job_id: str) -> dict[str, str]:
    """Return the saved cover letter text for a job."""
    text = storage.load_cover_letter(job_id)
    if text is None:
        raise HTTPException(status_code=404, detail="No cover letter found.")
    return {"job_id": job_id, "text": text}


@router.put("/{job_id}")
def save_cover_letter(
    job_id: str, body: CoverLetterSaveRequest
) -> dict[str, object]:
    """Save (or overwrite) the cover letter text for a job."""
    storage.save_cover_letter(job_id, body.text)
    return {"job_id": job_id, "saved": True}


@router.get("/{job_id}/export/txt")
def export_txt(job_id: str) -> Response:
    """Download the cover letter as a .txt file."""
    text = storage.load_cover_letter(job_id)
    if text is None:
        raise HTTPException(status_code=404, detail="No cover letter found.")
    return Response(
        content=text.encode("utf-8"),
        media_type="text/plain",
        headers={
            "Content-Disposition": (
                f'attachment; filename="cover_letter_{job_id}.txt"'
            )
        },
    )


@router.get("/{job_id}/export/pdf")
def export_pdf(job_id: str) -> StreamingResponse:
    """Download the cover letter as a .pdf file."""
    text = storage.load_cover_letter(job_id)
    if text is None:
        raise HTTPException(status_code=404, detail="No cover letter found.")

    pdf = FPDF()
    pdf.set_margins(20, 20, 20)
    pdf.set_auto_page_break(auto=True, margin=20)

    font_loaded = False
    if sys.platform == "win32":
        arial = (
            pathlib.Path(os.environ.get("SystemRoot", r"C:\Windows"))
            / "Fonts"
            / "arial.ttf"
        )
        if arial.exists():
            pdf.add_font("Arial", fname=str(arial))
            font_loaded = True

    pdf.add_page()
    pdf.set_font("Arial" if font_loaded else "Helvetica", size=11)

    cell_w = pdf.w - pdf.l_margin - pdf.r_margin
    for line in text.splitlines():
        pdf.multi_cell(cell_w, 6, line or " ")

    buf = io.BytesIO(pdf.output())
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="cover_letter_{job_id}.pdf"'
            )
        },
    )
