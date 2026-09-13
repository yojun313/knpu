import os
import re
import uuid
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse

from app.config import ALLOWED_EXTS, DATA_PATH, MAX_UPLOAD_BYTES
from app.db import notes_db, user_logs_db
from app.routes.dependencies import get_current_user
from app.services.transcribe_service import audio_path, start_transcription
from system.logging.user_log import insert_log

router = APIRouter()

# 목록에서는 무거운 필드(세그먼트/본문)를 제외한다
LIST_PROJECTION = {"_id": 0, "segments": 0, "text": 0}

AUDIO_MEDIA_TYPES = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".opus": "audio/ogg",
    ".flac": "audio/flac",
    ".wma": "audio/x-ms-wma",
    ".amr": "audio/amr",
    ".webm": "video/webm",
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".mkv": "video/x-matroska",
}


def _get_owned_note(uid: str, user: dict, projection=None):
    doc = notes_db.find_one({"uid": uid}, projection)
    if not doc:
        raise HTTPException(status_code=404, detail="노트를 찾을 수 없습니다")
    if doc.get("userUid") != user["uid"] and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="본인의 노트만 접근할 수 있습니다")
    return doc


@router.get("/api/notes")
def list_notes(q: str = None, user=Depends(get_current_user)):
    query = {"userUid": user["uid"]}
    if q:
        query["title"] = {"$regex": re.escape(q), "$options": "i"}
    items = list(notes_db.find(query, LIST_PROJECTION).sort("createdAt", -1).limit(500))
    for it in items:
        if isinstance(it.get("createdAt"), datetime):
            it["createdAt"] = it["createdAt"].isoformat()
        if isinstance(it.get("finishedAt"), datetime):
            it["finishedAt"] = it["finishedAt"].isoformat()
    return {"items": items}


@router.post("/api/notes")
async def create_note(
    file: UploadFile = File(...),
    language: str = Form("auto"),
    model: int = Form(2),
    user=Depends(get_current_user),
):
    orig_name = file.filename or "recording"
    ext = os.path.splitext(orig_name)[1].lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 파일 형식입니다: {ext or '(확장자 없음)'}",
        )

    uid = uuid.uuid4().hex
    path = os.path.join(DATA_PATH, f"{uid}{ext}")

    size = 0
    try:
        with open(path, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413, detail="파일이 너무 큽니다 (최대 2GB)"
                    )
                out.write(chunk)
    except HTTPException:
        if os.path.exists(path):
            os.remove(path)
        raise

    notes_db.insert_one(
        {
            "uid": uid,
            "userUid": user["uid"],
            "requester": user.get("name", ""),
            "title": os.path.splitext(orig_name)[0],
            "origFilename": orig_name,
            "ext": ext,
            "size": size,
            "language": language,
            "model": max(1, min(3, int(model))),
            "status": "queued",
            "stage": "변환 대기 중",
            "progress": 0,
            "duration": 0,
            "segments": [],
            "segCount": 0,
            "text": "",
            "error": None,
            "createdAt": datetime.now(),
            "finishedAt": None,
        }
    )
    start_transcription(uid)

    insert_log(
        user_logs_db,
        user["uid"],
        "whisper.note.create",
        "whisper",
        message=f"음성 인식 요청: {orig_name}",
        metadata={"size": size, "language": language, "model": int(model)},
    )
    return {"uid": uid}


@router.get("/api/notes/{uid}")
def get_note(uid: str, since: int = 0, user=Depends(get_current_user)):
    doc = _get_owned_note(uid, user, {"_id": 0})
    segments = doc.get("segments") or []
    since = max(0, since)
    doc["segments"] = segments[since:]
    doc["segOffset"] = since
    doc["segTotal"] = len(segments)
    if isinstance(doc.get("createdAt"), datetime):
        doc["createdAt"] = doc["createdAt"].isoformat()
    if isinstance(doc.get("finishedAt"), datetime):
        doc["finishedAt"] = doc["finishedAt"].isoformat()
    return doc


@router.patch("/api/notes/{uid}")
def rename_note(uid: str, body: dict, user=Depends(get_current_user)):
    _get_owned_note(uid, user, {"_id": 0, "uid": 1, "userUid": 1})
    title = (body.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="제목을 입력해 주세요")
    notes_db.update_one({"uid": uid}, {"$set": {"title": title[:200]}})
    return {"ok": True}


@router.post("/api/notes/{uid}/retry")
def retry_note(uid: str, user=Depends(get_current_user)):
    doc = _get_owned_note(uid, user, {"_id": 0})
    if doc.get("status") in ("queued", "processing"):
        raise HTTPException(status_code=409, detail="이미 변환이 진행 중입니다")
    if not os.path.isfile(audio_path(doc)):
        raise HTTPException(
            status_code=404, detail="음성 파일이 없습니다. 다시 업로드해 주세요"
        )
    start_transcription(uid)
    return {"ok": True}


@router.delete("/api/notes/{uid}")
def delete_note(uid: str, user=Depends(get_current_user)):
    doc = _get_owned_note(uid, user, {"_id": 0})
    notes_db.delete_one({"uid": uid})
    path = audio_path(doc)
    if os.path.isfile(path):
        os.remove(path)
    insert_log(
        user_logs_db,
        user["uid"],
        "whisper.note.delete",
        "whisper",
        message=f"노트 삭제: {doc.get('title', '')}",
    )
    return {"ok": True}


@router.get("/api/notes/{uid}/audio")
def get_audio(uid: str, request: Request, user=Depends(get_current_user)):
    doc = _get_owned_note(uid, user, {"_id": 0, "uid": 1, "userUid": 1, "ext": 1})
    path = audio_path(doc)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="음성 파일을 찾을 수 없습니다")

    media_type = AUDIO_MEDIA_TYPES.get(doc["ext"], "application/octet-stream")
    file_size = os.path.getsize(path)
    range_header = request.headers.get("range")

    # 브라우저 오디오 플레이어의 탐색(seek)에는 Range 응답이 필수다.
    # Starlette FileResponse는 Range를 처리하지 않으므로 직접 구현한다.
    if range_header:
        m = re.match(r"bytes=(\d*)-(\d*)", range_header)
        if not m:
            raise HTTPException(status_code=416, detail="잘못된 Range 헤더")
        start_s, end_s = m.groups()
        if start_s == "" and end_s == "":
            raise HTTPException(status_code=416, detail="잘못된 Range 헤더")
        if start_s == "":
            # suffix range: 마지막 N바이트
            length = min(int(end_s), file_size)
            start = file_size - length
            end = file_size - 1
        else:
            start = int(start_s)
            end = min(int(end_s), file_size - 1) if end_s else file_size - 1
        if start >= file_size or start > end:
            return Response(
                status_code=416, headers={"Content-Range": f"bytes */{file_size}"}
            )

        def iter_range(s=start, e=end):
            with open(path, "rb") as f:
                f.seek(s)
                remaining = e - s + 1
                while remaining > 0:
                    chunk = f.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(
            iter_range(),
            status_code=206,
            media_type=media_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(end - start + 1),
            },
        )

    return FileResponse(path, media_type=media_type, headers={"Accept-Ranges": "bytes"})


def _ts_srt(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int((t - int(t)) * 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


@router.get("/api/notes/{uid}/export")
def export_note(uid: str, fmt: str = "txt", user=Depends(get_current_user)):
    doc = _get_owned_note(uid, user, {"_id": 0})
    if doc.get("status") != "done":
        raise HTTPException(
            status_code=409, detail="변환이 완료된 노트만 내보낼 수 있습니다"
        )

    segments = doc.get("segments") or []
    title = doc.get("title") or "note"

    if fmt == "srt":
        lines = []
        for i, seg in enumerate(segments, 1):
            lines.append(
                f"{i}\n{_ts_srt(seg['start'])} --> {_ts_srt(seg['end'])}\n{seg['text']}\n"
            )
        content = "\n".join(lines)
        filename = f"{title}.srt"
    elif fmt == "time":
        content = "\n".join(
            f"[{_ts_srt(seg['start'])} - {_ts_srt(seg['end'])}] {seg['text']}"
            for seg in segments
        )
        filename = f"{title}_타임스탬프.txt"
    else:
        content = doc.get("text") or "\n".join(seg["text"] for seg in segments)
        filename = f"{title}.txt"

    return Response(
        content=content.encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="export.txt"; '
                f"filename*=UTF-8''{quote(filename)}"
            )
        },
    )
