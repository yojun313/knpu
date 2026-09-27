"""경찰청 표준 고소장 양식(docx)에 내용을 채우고 PDF로 변환한다."""

import copy
import logging
import secrets
import subprocess
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt
from docx.text.paragraph import Paragraph

from app.libs.pdf import get_libreoffice_cmd
from app.services.store import DOCS_DIR

logger = logging.getLogger(__name__)

TEMPLATE = (
    Path(__file__).resolve().parent.parent / "forms" / "고소장 표준 양식(경찰청).docx"
)

SECTION_ANCHORS = {
    "purpose": "(죄명 및 피고소인에 대한 처벌의사 기재)",
    "facts": "4. 범죄사실*",
    "reasons": "5. 고소이유",
    "evidence": "6. 증거자료",
    "others": "8. 기타",
}


def format_korean_date(value: str) -> str:
    if not value:
        return datetime.now().strftime("%Y년 %m월 %d일").replace(" 0", " ")
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            dt = datetime.strptime(value.strip(), fmt)
            return f"{dt.year}년 {dt.month}월 {dt.day}일"
        except ValueError:
            continue
    return value


def _find_paragraph(document, needle: str):
    for p in document.paragraphs:
        if needle in p.text:
            return p
    return None


def _insert_lines_after(anchor: Paragraph, text: str, align=WD_ALIGN_PARAGRAPH.JUSTIFY):
    """anchor 문단 바로 뒤에 text를 한 줄에 한 문단씩 넣는다(빈 줄 하나를 앞에 둔다).

    새 문단은 anchor의 문단 서식(pPr)을 복제하되 글자(run)는 비워서 만든다 —
    양식의 들여쓰기·줄간격을 유지하면서 굵은 제목 서식은 따라오지 않게 한다.
    """
    lines = [ln.rstrip() for ln in (text or "").splitlines()]
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return
    after = anchor
    for line in [""] + lines:
        el = copy.deepcopy(anchor._element)
        for child in list(el):
            if not child.tag.endswith("}pPr"):
                el.remove(child)
        after._element.addnext(el)
        para = Paragraph(el, anchor._parent)
        # 기준 문단(예: 오른쪽 정렬된 안내문)의 정렬을 물려받지 않게 명시한다
        para.alignment = align
        if line:
            run = para.add_run(line)
            run.font.size = Pt(10.5)
            run.bold = False
        after = para


def _set_cell_text(table, placeholder: str, value: str):
    for row in table.rows:
        for cell in row.cells:
            for para in cell.paragraphs:
                if para.text == placeholder:
                    para.text = value or ""


def render(party: dict, facts: dict, sections: dict, offense_label: str) -> dict:
    """문서를 만들어 {token, docx, pdf, filename} 을 돌려준다."""
    doc = Document(TEMPLATE)
    comp = party.get("complainant", {})
    susp = party.get("suspect", {})

    t0, t1, t2 = doc.tables[0], doc.tables[1], doc.tables[2]
    for key, ph in (
        ("name", "고소인 성명"),
        ("rrn", "고소인 주민등록번호"),
        ("address", "고소인 주소"),
        ("job", "고소인 직업"),
        ("phone", "고소인 전화"),
        ("email", "고소인 이메일"),
    ):
        _set_cell_text(t0, ph, comp.get(key, ""))
    for key, ph in (
        ("name", "피고소인 성명"),
        ("rrn", "피고소인 주민등록번호"),
        ("address", "피고소인 주소"),
        ("job", "피고소인 직업"),
        ("phone", "피고소인 전화"),
        ("email", "피고소인 이메일"),
    ):
        _set_cell_text(t1, ph, susp.get(key, "") or ("불상" if key == "name" else ""))
    _set_cell_text(t1, "피고소인 기타사항", sections.get("suspect_other", ""))

    # 관련 사건 체크 문장: 기존 양식 문장 뒤에 답을 붙인다
    answers = {
        "본 고소장과 같은 내용의 고소장을 다른 검찰청 또는 경찰서에 제출하거나 제출하였던 사실이 ": (
            "same_complaint",
            "본 고소장과 같은 내용의 고소장을 다른 검찰청 또는 경찰서에 제출하거나 제출하였던 사실을 ",
        ),
        "본 고소장에 기재된 범죄사실과 관련된 사건 또는 공범에 대하여 검찰청이나 경찰서에서 수사 중에 ": (
            "related_investigation",
            "본 고소장에 기재된 범죄사실과 관련된 사건 또는 공범에 대하여 검찰청이나 경찰서에서 수사 중에 있는지 ",
        ),
    }
    for row in t2.rows:
        for cell in row.cells:
            for para in cell.paragraphs:
                if para.text in answers:
                    key, unknown_text = answers[para.text]
                    value = facts.get(key) or "없음"
                    if value == "모름":
                        para.text = unknown_text
                    run = para.add_run(f" {value}")
                    run.bold = True

    for key, anchor_text in SECTION_ANCHORS.items():
        anchor = _find_paragraph(doc, anchor_text)
        if anchor is not None:
            _insert_lines_after(anchor, sections.get(key, ""))

    date_text = format_korean_date(party.get("filing_date", ""))
    pledge = _find_paragraph(doc, "무고죄로 처벌받을 것임을 서약합니다.")
    if pledge is not None:
        _insert_lines_after(pledge, date_text, align=WD_ALIGN_PARAGRAPH.RIGHT)

    # 서명란: '고소인 ____ (인)*'의 가운데 공백 run 자리에 이름을 넣는다(글자 서식 유지)
    signer = next(
        (p for p in doc.paragraphs if "고소인" in p.text and "(인)*" in p.text), None
    )
    if signer is not None and comp.get("name") and len(signer.runs) >= 3:
        blank = signer.runs[1]
        width = len(blank.text)
        name = comp["name"].strip()
        pad = max(2, width - len(name) * 2)  # 한글은 공백 두 칸 너비
        blank.text = " " * (pad // 2) + name + " " * (pad - pad // 2)

    station = party.get("station", "")
    tail = _find_paragraph(doc, "고소대리의 경우에는 제출인을 기재하여야 합니다.")
    if tail is not None and station:
        _insert_lines_after(tail, f"\n{station} 귀중", align=WD_ALIGN_PARAGRAPH.RIGHT)

    token = secrets.token_urlsafe(18)
    docx_path = DOCS_DIR / f"{token}.docx"
    doc.save(docx_path)
    pdf_ok = _to_pdf(docx_path)

    stamp = datetime.now().strftime("%Y%m%d")
    return {
        "token": token,
        "filename": f"고소장_{offense_label}_{stamp}",
        "pdf": pdf_ok,
        "created": datetime.now().isoformat(timespec="seconds"),
    }


def _to_pdf(docx_path: Path) -> bool:
    try:
        subprocess.run(
            [
                get_libreoffice_cmd(),
                "--headless",
                "--convert-to",
                "pdf",
                str(docx_path),
                "--outdir",
                str(docx_path.parent),
            ],
            check=True,
            timeout=120,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return docx_path.with_suffix(".pdf").exists()
    except Exception as e:
        logger.error("PDF 변환 실패: %s", e)
        return False
