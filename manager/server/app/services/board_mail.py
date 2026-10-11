"""Durable board reply mail delivery, shared by all manager server workers."""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from pymongo import ReturnDocument
from app.db import bug_board_db, suggestion_board_db, user_db
from system.endpoints import public_url
from system.notify.mail import sendEmail

logger = logging.getLogger(__name__)


def send_next_reply_notification() -> bool:
    bug_processed = _send_next_reply_notification(bug_board_db, "bug")
    suggestion_processed = _send_next_reply_notification(
        suggestion_board_db, "suggestion"
    )
    return bug_processed or suggestion_processed


def _send_next_reply_notification(collection, board: str) -> bool:
    now = datetime.now(timezone.utc)
    claim = str(uuid.uuid4())
    due = {
        "$or": [
            {
                "mail.status": {"$in": ["pending", "retry"]},
                "mail.next_attempt": {"$lte": now},
            },
            {"mail.status": "sending", "mail.lease_until": {"$lte": now}},
        ]
    }
    candidate = collection.find_one(
        {"replies": {"$elemMatch": due}}, {"uid": 1, "replies": 1}
    )
    if not candidate:
        return False

    def due_now(reply):
        state = reply.get("mail") or {}
        when = (
            state.get("lease_until")
            if state.get("status") == "sending"
            else state.get("next_attempt")
        )
        if state.get("status") not in ("pending", "retry", "sending") or not isinstance(
            when, datetime
        ):
            return False
        return (
            when.replace(tzinfo=timezone.utc) <= now
            if when.tzinfo is None
            else when <= now
        )

    index = next(
        (i for i, reply in enumerate(candidate["replies"]) if due_now(reply)), None
    )
    if index is None:
        return False
    prefix = f"replies.{index}"
    # The UID guard keeps this safe even if a future feature reorders replies.
    selector = {
        "uid": candidate["uid"],
        f"{prefix}.uid": candidate["replies"][index]["uid"],
        "$or": [
            {
                f"{prefix}.mail.status": {"$in": ["pending", "retry"]},
                f"{prefix}.mail.next_attempt": {"$lte": now},
            },
            {
                f"{prefix}.mail.status": "sending",
                f"{prefix}.mail.lease_until": {"$lte": now},
            },
        ],
    }
    doc = collection.find_one_and_update(
        selector,
        {
            "$set": {
                f"{prefix}.mail.status": "sending",
                f"{prefix}.mail.claim": claim,
                f"{prefix}.mail.lease_until": now + timedelta(minutes=5),
            },
            "$inc": {f"{prefix}.mail.attempts": 1},
        },
        return_document=ReturnDocument.AFTER,
    )
    if not doc:
        return False
    reply = next(
        r for r in doc["replies"] if (r.get("mail") or {}).get("claim") == claim
    )
    selector = {
        "uid": doc["uid"],
        f"{prefix}.uid": reply["uid"],
        f"{prefix}.mail.claim": claim,
        f"{prefix}.mail.status": "sending",
    }
    writer = user_db.find_one({"uid": doc.get("writerUid")}, {"email": 1}) or {}
    recipient = (writer.get("email") or "").strip()
    status = "sent"
    fields = {}
    try:
        if not recipient:
            status = "skipped"
        else:
            link = (
                public_url("manager")
                + "/board?"
                + urlencode({"tab": board, "uid": doc["uid"]})
            )
            label = "버그리포트" if board == "bug" else "건의·제안사항"
            sendEmail(
                recipient,
                f"[KNPU FPEI] {label}에 관리자 답변이 등록되었습니다",
                f"{label}: {doc.get('bugTitle' if board == 'bug' else 'title', '')}\n"
                f"답변자: {reply.get('writerName', '관리자')}\n\n{reply['text']}\n\n"
                f"게시판에서 확인하기: {link}\n\n매니저 앱의 {label}에서도 확인할 수 있습니다.",
            )
    except Exception:
        status = "retry"
        delay = min(3600, 30 * 2 ** min(reply["mail"].get("attempts", 1), 7))
        fields[f"{prefix}.mail.next_attempt"] = now + timedelta(seconds=delay)
        # Avoid logging credentials or recipient addresses from SMTP exceptions.
        logger.warning(
            "Board reply email delivery failed; retry queued (board=%s, uid=%s)",
            board,
            doc["uid"],
        )
    fields[f"{prefix}.mail.status"] = status
    fields[f"{prefix}.mail.updated_at"] = datetime.now(timezone.utc)
    collection.update_one(
        selector,
        {
            "$set": fields,
            "$unset": {
                f"{prefix}.mail.claim": "",
                f"{prefix}.mail.lease_until": "",
            },
        },
    )
    return True


async def reply_notification_loop():
    while True:
        try:
            processed = await asyncio.to_thread(send_next_reply_notification)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("Board reply notification queue unavailable; retrying later")
            processed = False
        await asyncio.sleep(1 if processed else 10)
