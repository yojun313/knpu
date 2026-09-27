import asyncio
import json
import logging
import re
from collections import defaultdict
from datetime import date

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from system.llm import LLMError

from app.legal import kb
from app.legal.crimes import CRIMES, FACTS, schema
from app.libs.mail import sendEmail
from app.services import drafter, document, intake, ratelimit, store
from app.services.store import DOCS_DIR

logger = logging.getLogger(__name__)
router = APIRouter()

_case_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


def _ndjson(gen):
    async def body():
        async for ev in gen:
            yield json.dumps(ev, ensure_ascii=False) + "\n"

    return StreamingResponse(
        body(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _load_or_404(case_id: str) -> dict:
    case = store.load(case_id)
    if not case:
        raise HTTPException(
            404, "사건을 찾을 수 없습니다. 보존 기간이 지나 삭제되었을 수 있습니다."
        )
    return case


def _public(case: dict) -> dict:
    """브라우저로 돌려줄 사건 — 주민등록번호는 절대 내보내지 않는다."""
    party = json.loads(json.dumps(case.get("party") or {}))
    for side in ("complainant", "suspect"):
        if isinstance(party.get(side), dict):
            party[side]["has_rrn"] = bool(party[side].pop("rrn", ""))
    return {
        "id": case["id"],
        "mode": case["mode"],
        "created": case["created"],
        "updated": case["updated"],
        "messages": [
            {"role": m["role"], "content": m["content"]} for m in case["messages"]
        ],
        "party": party,
        "state": intake.case_state(case),
        "analysis": case.get("analysis"),
        "draft": case.get("draft"),
        "review": case.get("review"),
        "files": case.get("files"),
    }


# ── 메타 ─────────────────────────────────────────────────────────────────────
@router.get("/meta")
def meta():
    return {
        **schema(),
        "kb": kb.meta(),
        "starter_suggestions": intake.STARTER_SUGGESTIONS,
    }


@router.get("/legal/search")
def legal_search(q: str = "", crime: str | None = None):
    q = q.strip()[:200]
    if not q:
        return {"statutes": [], "precedents": []}
    return {
        "statutes": [intake._statute_card(s) for s in kb.search_statutes(q, k=5)],
        "precedents": [
            intake._precedent_card(p)
            for p in kb.search_precedents(q, crime if crime in CRIMES else None, k=4)
        ],
    }


# ── 사건 ─────────────────────────────────────────────────────────────────────
class CreateCase(BaseModel):
    mode: str = Field("chat", pattern="^(chat|form)$")
    crime_type: str | None = None


@router.post("/cases")
def create_case(body: CreateCase, request: Request):
    ratelimit.check(request, "create", 30, 600)
    case = store.create(body.mode)
    if body.crime_type in CRIMES:
        case["crime_type"] = body.crime_type
    if body.mode == "chat":
        case["messages"].append(
            {"role": "assistant", "content": intake.GREETING, "ts": case["created"]}
        )
    store.save(case)
    return _public(case)


@router.get("/cases/{case_id}")
def get_case(case_id: str):
    return _public(_load_or_404(case_id))


@router.delete("/cases/{case_id}")
def delete_case(case_id: str):
    store.delete(case_id)
    return {"ok": True}


class ChatIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


@router.post("/cases/{case_id}/chat")
async def chat(case_id: str, body: ChatIn, request: Request):
    ratelimit.check(request, "chat", 40, 600)
    _load_or_404(case_id)

    async def run():
        async with _case_locks[case_id]:
            case = store.load(case_id)
            try:
                async for ev in intake.chat_turn(case, body.message.strip()):
                    yield ev
            finally:
                store.save(case)

    return _ndjson(run())


class FactsIn(BaseModel):
    crime_type: str | None = None
    facts: dict[str, str] = {}


@router.put("/cases/{case_id}/facts")
async def put_facts(case_id: str, body: FactsIn):
    async with _case_locks[case_id]:
        case = _load_or_404(case_id)
        if body.crime_type is not None:
            if body.crime_type not in CRIMES:
                raise HTTPException(400, "알 수 없는 사건 유형입니다.")
            case["crime_type"] = body.crime_type
        for k, v in body.facts.items():
            if k in FACTS:
                v = (v or "").strip()[:4000]
                if v:
                    case["facts"][k] = v
                else:
                    case["facts"].pop(k, None)
        store.save(case)
        return {"state": intake.case_state(case)}


# ── 문서 생성 ─────────────────────────────────────────────────────────────────
class Person(BaseModel):
    name: str = Field("", max_length=60)
    rrn: str = Field("", max_length=20)
    address: str = Field("", max_length=200)
    job: str = Field("", max_length=60)
    phone: str = Field("", max_length=30)
    email: str = Field("", max_length=120)


class PartyIn(BaseModel):
    complainant: Person
    suspect: Person = Person()
    station: str = Field(..., min_length=2, max_length=60)
    filing_date: str = Field("", max_length=20)
    keep_rrn: bool = False  # 이전에 입력한 주민번호를 그대로 쓸지(다시 만들기)


_RRN_RE = re.compile(r"^\d{6}-?\d{7}$")


def _merge_party(case: dict, body: PartyIn) -> dict:
    old = case.get("party") or {}
    party = body.model_dump()
    party.pop("keep_rrn", None)
    for side in ("complainant", "suspect"):
        p = party[side]
        p["rrn"] = p["rrn"].strip()
        if not p["rrn"] and body.keep_rrn:
            p["rrn"] = (old.get(side) or {}).get("rrn", "")
        if p["rrn"]:
            if not _RRN_RE.match(p["rrn"]):
                raise HTTPException(
                    400,
                    f"{'고소인' if side == 'complainant' else '피고소인'} 주민등록번호 형식이 올바르지 않습니다.",
                )
            digits = p["rrn"].replace("-", "")
            p["rrn"] = f"{digits[:6]}-{digits[6:]}"
    c = party["complainant"]
    if not c["name"].strip() or not c["phone"].strip() or not c["address"].strip():
        raise HTTPException(400, "고소인 성명·주소·연락처는 반드시 입력해야 합니다.")
    if not c["rrn"]:
        raise HTTPException(400, "고소인 주민등록번호를 입력해 주세요.")
    party["filing_date"] = party["filing_date"] or date.today().isoformat()
    return party


@router.post("/cases/{case_id}/generate")
async def generate(case_id: str, body: PartyIn, request: Request):
    ratelimit.check(request, "generate", 8, 600)
    case = _load_or_404(case_id)
    if case.get("crime_type") not in CRIMES:
        raise HTTPException(400, "사건 유형이 정해지지 않았습니다.")
    if not any(
        str(case["facts"].get(k, "")).strip()
        for k in ("deception", "disposition", "false_reason", "insurance_reason")
    ):
        raise HTTPException(
            400,
            "고소장을 쓰기에 사건 내용이 부족합니다. 어떤 거짓말에 속아 무엇을 넘겼는지 먼저 알려 주세요.",
        )
    party = _merge_party(case, body)

    async def run():
        async with _case_locks[case_id]:
            fresh = store.load(case_id)
            fresh["party"] = party
            store.save(fresh)
            try:
                async for ev in drafter.generate(fresh):
                    yield ev
            except LLMError as e:
                logger.error("고소장 생성 실패: %s", e)
                yield {
                    "type": "error",
                    "message": "AI 서버 응답에 실패했습니다. 잠시 후 다시 시도해 주세요.",
                }
            except Exception:
                logger.exception("고소장 생성 중 오류")
                yield {
                    "type": "error",
                    "message": "고소장을 만드는 중 오류가 발생했습니다.",
                }
            finally:
                store.save(fresh)

    return _ndjson(run())


class RenderIn(BaseModel):
    sections: dict[str, str]


@router.post("/cases/{case_id}/render")
async def rerender(case_id: str, body: RenderIn, request: Request):
    """사용자가 고친 문장으로 문서만 다시 만든다(AI 호출 없음)."""
    ratelimit.check(request, "render", 30, 600)
    async with _case_locks[case_id]:
        case = _load_or_404(case_id)
        if not case.get("draft") or not case.get("party"):
            raise HTTPException(400, "먼저 고소장을 생성해 주세요.")
        sections = {
            k: (body.sections.get(k, case["draft"].get(k, "")) or "")[:20000]
            for k in drafter.SECTION_KEYS
        }
        allowed = drafter.allowed_articles(
            [s for s in (case["analysis"] or {}).get("statutes", [])]
        )
        issues = drafter.rule_check(sections, case["facts"], allowed)
        old = case.get("files") or {}
        files = await asyncio.to_thread(
            document.render,
            case["party"],
            case["facts"],
            sections,
            (case.get("analysis") or {}).get("offense", "사기"),
        )
        for ext in ("docx", "pdf"):
            if old.get("token"):
                (DOCS_DIR / f"{old['token']}.{ext}").unlink(missing_ok=True)
        case["draft"], case["files"] = sections, files
        case["review"] = {"issues": issues, "revised": False, "edited": True}
        store.save(case)
        return {"files": files, "review": case["review"], "draft": sections}


class EmailIn(BaseModel):
    to: str = Field(..., max_length=120)
    kind: str = Field("self", pattern="^(self|submit)$")


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@router.post("/cases/{case_id}/email")
async def email(case_id: str, body: EmailIn, request: Request):
    ratelimit.check(request, "email", 5, 600)
    case = _load_or_404(case_id)
    files = case.get("files")
    if not files:
        raise HTTPException(400, "먼저 고소장을 생성해 주세요.")
    if not _EMAIL_RE.match(body.to.strip()):
        raise HTTPException(400, "이메일 주소 형식이 올바르지 않습니다.")
    name = (case.get("party") or {}).get("complainant", {}).get("name", "")
    attach = DOCS_DIR / f"{files['token']}.docx"
    named = DOCS_DIR / f"{files['filename']}.docx"
    if body.kind == "self":
        title = "[FPEI AI 고소장] 고소장 초안이 준비되었습니다"
        text = (
            "안녕하세요.\n요청하신 AI 고소장 초안을 첨부해 드립니다.\n\n"
            "첨부된 문서는 AI가 작성한 초안입니다. 제출 전 사실관계와 표현을 반드시 다시 확인하시고, "
            "고소인 서명·날인 후 제출해 주세요.\n\n감사합니다."
        )
    else:
        title = f"[FPEI AI 고소장 제출] {name}님의 고소장입니다"
        text = f"{name}님의 고소장을 송부합니다.\n첨부 파일을 확인해 주시기 바랍니다."
    try:
        # 첨부 파일명은 사람이 읽을 수 있게(토큰 이름 대신) 잠시 복사해 보낸다
        named.write_bytes(attach.read_bytes())
        await asyncio.to_thread(sendEmail, body.to.strip(), title, text, str(named))
    except Exception as e:
        logger.error("메일 발송 실패: %s", e)
        raise HTTPException(
            502, "메일을 보내지 못했습니다. 잠시 후 다시 시도해 주세요."
        )
    finally:
        named.unlink(missing_ok=True)
    return {"ok": True}


# ── 파일 ─────────────────────────────────────────────────────────────────────
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")


@router.get("/files/{case_id}/{kind}")
def get_file(case_id: str, kind: str, download: int = 0):
    case = _load_or_404(case_id)
    files = case.get("files") or {}
    token = files.get("token", "")
    if kind not in ("docx", "pdf") or not _TOKEN_RE.match(token):
        raise HTTPException(404, "파일이 없습니다.")
    path = DOCS_DIR / f"{token}.{kind}"
    if not path.exists():
        raise HTTPException(404, "파일이 없습니다.")
    media = (
        "application/pdf"
        if kind == "pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    filename = f"{files.get('filename', '고소장')}.{kind}"
    resp = FileResponse(
        path,
        media_type=media,
        filename=filename,
        content_disposition_type="attachment"
        if (download or kind == "docx")
        else "inline",
    )
    resp.headers["Cache-Control"] = "no-store"
    return resp
