import asyncio
import json
import logging
import re
from collections import defaultdict
from datetime import date

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from system.llm import LLMError

from app.legal import kb
from app.legal.crimes import CRIMES, FACTS, schema
from app.libs.mail import sendEmail
from app.services import drafter, document, intake, ratelimit, store

logger = logging.getLogger(__name__)
router = APIRouter()

_case_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

# 사건 키는 이 헤더로만 받는다. URL·쿠키·본문에 넣으면 접속 기록이나 브라우저에 남는다.
KEY_HEADER = "X-Case-Key"
_NOT_FOUND = "작성 중인 내용을 찾을 수 없습니다. 새로 고침하거나 다시 접속하면 이전 내용은 열 수 없습니다."


def prune_locks() -> None:
    """사용하지 않는 사건 잠금을 정리한다(메모리 보호)."""
    for case_id, lock in list(_case_locks.items()):
        if not lock.locked():
            _case_locks.pop(case_id, None)


def _key(request: Request) -> bytes:
    key = store.decode_key(request.headers.get(KEY_HEADER))
    if not key:
        raise HTTPException(404, _NOT_FOUND)
    return key


def _ndjson(gen):
    async def body():
        async for ev in gen:
            yield json.dumps(ev, ensure_ascii=False) + "\n"

    return StreamingResponse(
        body(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


def _load_or_404(case_id: str, key: bytes) -> dict:
    case = store.load(case_id, key)
    if not case:
        raise HTTPException(404, _NOT_FOUND)
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
        "files": _public_files(case.get("files")),
    }


def _public_files(files: dict | None) -> dict | None:
    """문서 저장 토큰은 브라우저에 내보내지 않는다(파일은 사건 id와 키로만 받는다)."""
    if not files:
        return None
    return {
        "pdf": files.get("pdf"),
        "filename": files.get("filename"),
        "created": files.get("created"),
        "version": (files.get("token") or "")[:8],
    }


# ── 메타 ─────────────────────────────────────────────────────────────────────
@router.get("/meta")
def meta():
    return {
        **schema(),
        "kb": kb.meta(),
        "starter_suggestions": intake.STARTER_SUGGESTIONS,
        "retention_hours": store.RETENTION_SEC / 3600,
    }


@router.get("/legal/search")
def legal_search(request: Request, q: str = "", crime: str | None = None):
    ratelimit.check(request, "search", 60, 600)
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
    case, key = store.create(body.mode)
    if body.crime_type in CRIMES:
        case["crime_type"] = body.crime_type
    if body.mode == "chat":
        case["messages"].append(
            {"role": "assistant", "content": intake.GREETING, "ts": case["created"]}
        )
    store.save(case, key)
    # 키는 이 응답에서 한 번만 내보낸다. 서버는 키를 보관하지 않는다.
    return {**_public(case), "key": store.encode_key(key)}


@router.get("/cases/{case_id}")
def get_case(case_id: str, request: Request):
    ratelimit.check(request, "read", 300, 600)
    return _public(_load_or_404(case_id, _key(request)))


def _discard(case_id: str, key: bytes | None) -> None:
    if store.delete(case_id, key):
        lock = _case_locks.get(case_id)
        if lock and not lock.locked():
            _case_locks.pop(case_id, None)


@router.delete("/cases/{case_id}")
def delete_case(case_id: str, request: Request):
    ratelimit.check(request, "delete", 60, 600)
    _discard(case_id, _key(request))
    return {"ok": True}


@router.post("/cases/{case_id}/discard", status_code=204)
async def discard_case(case_id: str, request: Request):
    """페이지를 떠날 때 navigator.sendBeacon 으로 보내는 삭제 요청(본문 = 사건 키).

    sendBeacon 은 헤더를 붙일 수 없어 키를 text/plain 본문으로 받는다.
    """
    ratelimit.check(request, "delete", 60, 600)
    raw = (await request.body())[:128].decode("ascii", "ignore").strip()
    _discard(case_id, store.decode_key(raw))
    return Response(status_code=204)


class ChatIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


@router.post("/cases/{case_id}/chat")
async def chat(case_id: str, body: ChatIn, request: Request):
    ratelimit.check(request, "chat", 40, 600)
    key = _key(request)
    _load_or_404(case_id, key)

    async def run():
        async with _case_locks[case_id]:
            case = store.load(case_id, key)
            if not case:
                yield {"type": "error", "message": _NOT_FOUND}
                return
            try:
                async for ev in intake.chat_turn(case, body.message.strip()):
                    yield ev
            except Exception:
                logger.exception("채팅 처리 중 오류")
                yield {
                    "type": "error",
                    "message": "답변을 만드는 중 오류가 발생했습니다. 잠시 후 다시 보내 주시기 바랍니다.",
                }
            finally:
                store.save(case, key)

    return _ndjson(run())


class FactsIn(BaseModel):
    crime_type: str | None = None
    facts: dict[str, str] = {}


@router.put("/cases/{case_id}/facts")
async def put_facts(case_id: str, body: FactsIn, request: Request):
    ratelimit.check(request, "facts", 300, 600)
    key = _key(request)
    async with _case_locks[case_id]:
        case = _load_or_404(case_id, key)
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
        store.save(case, key)
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
        raise HTTPException(400, "고소인 주민등록번호를 입력해 주시기 바랍니다.")
    party["filing_date"] = party["filing_date"] or date.today().isoformat()
    return party


@router.post("/cases/{case_id}/generate")
async def generate(case_id: str, body: PartyIn, request: Request):
    ratelimit.check(request, "generate", 8, 600)
    key = _key(request)
    case = _load_or_404(case_id, key)
    if case.get("crime_type") not in CRIMES:
        raise HTTPException(400, "사건 유형이 정해지지 않았습니다.")
    # 피고소인이 무엇을 했는지 설명하는 항목이 하나도 없으면 범죄사실을 쓸 수 없다
    act_keys = (
        "deception",
        "disposition",
        "false_reason",
        "insurance_reason",
        "act_description",
        "words_used",
        "entrustment",
        "duty",
        "wage_details",
        "document_details",
    )
    if not any(str(case["facts"].get(k, "")).strip() for k in act_keys):
        raise HTTPException(
            400,
            "고소장을 쓰기에 사건 내용이 부족합니다. 상대방이 언제, 무엇을 했는지 먼저 알려 주시기 바랍니다.",
        )
    party = _merge_party(case, body)

    async def run():
        async with _case_locks[case_id]:
            fresh = store.load(case_id, key)
            if not fresh:
                yield {"type": "error", "message": _NOT_FOUND}
                return
            old_token = (fresh.get("files") or {}).get("token")
            fresh["party"] = party
            store.save(fresh, key)
            try:
                async for ev in drafter.generate(fresh, key):
                    if ev.get("type") == "result":
                        ev = {**ev, "files": _public_files(ev.get("files"))}
                    yield ev
            except LLMError as e:
                logger.error("고소장 생성 실패: %s", e)
                yield {
                    "type": "error",
                    "message": "AI 서버 응답에 실패했습니다. 잠시 후 다시 시도해 주시기 바랍니다.",
                }
            except Exception:
                logger.exception("고소장 생성 중 오류")
                yield {
                    "type": "error",
                    "message": "고소장을 만드는 중 오류가 발생했습니다.",
                }
            finally:
                store.save(fresh, key)
                new_token = (fresh.get("files") or {}).get("token")
                if old_token and old_token != new_token:
                    store.delete_docs(old_token)

    return _ndjson(run())


class RenderIn(BaseModel):
    sections: dict[str, str]


@router.post("/cases/{case_id}/render")
async def rerender(case_id: str, body: RenderIn, request: Request):
    """사용자가 고친 문장으로 문서만 다시 만든다(AI 호출 없음)."""
    ratelimit.check(request, "render", 30, 600)
    key = _key(request)
    async with _case_locks[case_id]:
        case = _load_or_404(case_id, key)
        if not case.get("draft") or not case.get("party"):
            raise HTTPException(400, "먼저 고소장을 생성해 주시기 바랍니다.")
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
            CRIMES[case["crime_type"]].label
            if case.get("crime_type") in CRIMES
            else "고소장",
            key,
        )
        store.delete_docs(old.get("token"))
        case["draft"], case["files"] = sections, files
        case["review"] = {"issues": issues, "revised": False, "edited": True}
        store.save(case, key)
        return {
            "files": _public_files(files),
            "review": case["review"],
            "draft": sections,
        }


class EmailIn(BaseModel):
    to: str = Field(..., max_length=120)
    kind: str = Field("self", pattern="^(self|submit)$")


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@router.post("/cases/{case_id}/email")
async def email(case_id: str, body: EmailIn, request: Request):
    ratelimit.check(request, "email", 5, 600)
    case = _load_or_404(case_id, _key(request))
    files = case.get("files")
    if not files:
        raise HTTPException(400, "먼저 고소장을 생성해 주시기 바랍니다.")
    if not _EMAIL_RE.match(body.to.strip()):
        raise HTTPException(400, "이메일 주소 형식이 올바르지 않습니다.")
    name = (case.get("party") or {}).get("complainant", {}).get("name", "")
    data = store.read_doc(files.get("token", ""), "docx", _key(request))
    if data is None:
        raise HTTPException(404, "파일이 없습니다.")
    if body.kind == "self":
        title = "[FPEI AI 고소장] 고소장 초안이 준비되었습니다"
        text = (
            "안녕하십니까.\n요청하신 AI 고소장 초안을 첨부해 드립니다.\n\n"
            "첨부된 문서는 AI가 작성한 초안입니다. 제출 전 사실관계와 표현을 반드시 다시 확인하시고, "
            "고소인 서명·날인 후 제출해 주시기 바랍니다.\n\n감사합니다."
        )
    else:
        title = f"[FPEI AI 고소장 제출] {name}님의 고소장입니다"
        text = f"{name}님의 고소장을 송부합니다.\n첨부 파일을 확인해 주시기 바랍니다."
    try:
        await asyncio.to_thread(
            sendEmail,
            body.to.strip(),
            title,
            text,
            (f"{files['filename']}.docx", data),
        )
    except Exception as e:
        # 예외 메시지에 받는 주소가 들어갈 수 있어 종류만 남긴다
        logger.error("메일 발송 실패: %s", type(e).__name__)
        raise HTTPException(
            502, "메일을 보내지 못했습니다. 잠시 후 다시 시도해 주시기 바랍니다."
        )
    return {"ok": True}


# ── 파일 ─────────────────────────────────────────────────────────────────────
_MEDIA = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.get("/files/{case_id}/{kind}")
def get_file(case_id: str, kind: str, request: Request):
    """복호화한 문서를 돌려준다. 브라우저는 fetch로 받아 메모리(blob)에서만 연다."""
    ratelimit.check(request, "file", 120, 600)
    key = _key(request)
    case = _load_or_404(case_id, key)
    files = case.get("files") or {}
    data = store.read_doc(files.get("token", ""), kind, key) if kind in _MEDIA else None
    if data is None:
        raise HTTPException(404, "파일이 없습니다.")
    return Response(
        data,
        media_type=_MEDIA[kind],
        headers={"Cache-Control": "no-store", "Content-Disposition": "attachment"},
    )
