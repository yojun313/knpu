import subprocess
import platform
from pathlib import Path

def get_libreoffice_cmd() -> str:
    system = platform.system()

    if system == "Darwin":  
        return "/Applications/LibreOffice.app/Contents/MacOS/soffice"
    elif system == "Linux":  
        return "libreoffice"
    else:
        raise RuntimeError(f"Unsupported OS: {system}")


def convert_to_pdf(docx_path: Path) -> Path:
    pdf_path = docx_path.with_suffix(".pdf")

    libreoffice_cmd = get_libreoffice_cmd()

    subprocess.run([
        libreoffice_cmd,
        "--headless",
        "--convert-to", "pdf",
        str(docx_path),
        "--outdir", str(docx_path.parent)
    ], check=True)

    return pdf_path
