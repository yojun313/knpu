from fastapi.responses import FileResponse
from fastapi import APIRouter
from app.libs.exceptions import NotFoundException
from app.libs.form import storage_path

router = APIRouter()

@router.get("/pdf/{file_id}")
def preview_pdf(file_id: str):
    pdf_path = storage_path / f"{file_id}.pdf"
    if not pdf_path.exists():
        raise NotFoundException("PDF file not found")

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"{file_id}.pdf",
        headers={"Content-Disposition": "inline"}
    )
