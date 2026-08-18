"""웹소켓 — 인증 이후로는 서버→클라이언트 단방향 푸시만 한다(hub.py 설명 참고).

AuthMiddleware는 non-HTTP 스코프(웹소켓)를 그냥 통과시키므로, 여기서 반드시
직접 인증해야 한다(PLAN.md 5.3) — 빠뜨리면 누구나 관리자 콘솔 채널에 붙을 수 있다.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.auth import authenticate_websocket, verify_respondent_token
from app.db import collections_db, surveys_db, projects_db, respondents_db, responses_db
from app.services.hub import hub
from app.routes.collection_routes import respondent_progress_summary

router = APIRouter()


async def _project_for_collection(collection: dict) -> dict | None:
    survey = await surveys_db.find_one({"_id": collection["survey_id"]})
    if not survey:
        return None
    return await projects_db.find_one({"_id": survey["project_id"]})


@router.websocket("/ws/console/{collection_id}")
async def ws_console(ws: WebSocket, collection_id: str):
    user = await authenticate_websocket(ws)
    if not user:
        await ws.close(code=1008)
        return

    collection = await collections_db.find_one({"_id": collection_id})
    if not collection:
        await ws.close(code=1008)
        return
    project = await _project_for_collection(collection)
    if not project or (
        project.get("owner_uid") != user["uid"] and user.get("role") != "admin"
    ):
        await ws.close(code=1008)
        return

    await ws.accept()
    await hub.join(collection_id, ws, "admin")

    try:
        survey = await surveys_db.find_one({"_id": collection["survey_id"]})
        respondents = [
            r async for r in respondents_db.find({"collection_id": collection_id})
        ]
        responses_by_rid = {
            r["respondent_id"]: r.get("answers", {})
            async for r in responses_db.find({"collection_id": collection_id})
        }
        online = hub.online_respondents(collection_id)
        snapshot = [
            {
                "id": r["_id"],
                "label": r["label"],
                "status": r.get("status", "not_started"),
                "online": r["_id"] in online,
                **respondent_progress_summary(
                    survey["matrices"], responses_by_rid.get(r["_id"], {})
                ),
            }
            for r in respondents
        ]
        await ws.send_json(
            {
                "event": "snapshot",
                "respondents": snapshot,
                "round": collection.get("round", 1),
            }
        )

        while True:
            # 관리자 소켓은 클라이언트→서버 메시지를 쓰지 않는다(문항 수정은 기존
            # HTTP PUT /api/projects/{id}/survey를 그대로 쓴다) — 여기선 연결
            # 유지·끊김 감지만 한다.
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await hub.leave(collection_id, ws)


@router.websocket("/ws/respond/{token}")
async def ws_respond(ws: WebSocket, token: str):
    collection = await collections_db.find_one({"access_token": token})
    if not collection:
        await ws.close(code=1008)
        return

    await ws.accept()

    # 응답자는 쿠키가 아니라 로컬스토리지의 Bearer 토큰으로 인증하므로, accept
    # 이후 도착하는 첫 메시지로 신원을 확인한다(PLAN.md 7.2의 auth 이벤트).
    try:
        first = await ws.receive_json()
    except Exception:
        await ws.close(code=1008)
        return
    if first.get("type") != "auth":
        await ws.close(code=1008)
        return
    payload = verify_respondent_token(first.get("token", ""))
    if not payload or payload["collection_id"] != collection["_id"]:
        await ws.close(code=1008)
        return

    respondent_id = payload["respondent_id"]
    room_id = collection["_id"]
    await hub.join(room_id, ws, f"respondent:{respondent_id}")

    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await hub.leave(room_id, ws)
