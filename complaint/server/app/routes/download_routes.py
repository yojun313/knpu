from fastapi.responses import FileResponse
from fastapi import APIRouter
from app.libs.exceptions import NotFoundException
from app.libs.form import storage_path

router = APIRouter()

@router.get("/word/{file_id}")
def download_word(file_id: str):
    path = storage_path / f"{file_id}.docx"
    if not path.exists():
        raise NotFoundException("Word file not found")

    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"{file_id}.docx"
    )


@router.get("/pdf/{file_id}")
def download_pdf(file_id: str):
    path = storage_path / f"{file_id}.pdf"
    if not path.exists():
        raise NotFoundException("PDF file not found")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"{file_id}.pdf"
    )
