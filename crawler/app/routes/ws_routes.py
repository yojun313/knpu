import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()

queue_manager = None


def set_queue_manager(qm):
    global queue_manager
    queue_manager = qm


@router.get("/ws/dashboard")
def dashboard_ws_http_hint():
    return {
        "detail": "This endpoint is WebSocket-only. Use ws://<host>:3005/api/ws/dashboard",
    }


@router.websocket("/ws/dashboard")
async def dashboard_ws(websocket: WebSocket):
    if queue_manager is None:
        await websocket.close(code=1011, reason="queue_manager not initialized")
        return

    await websocket.accept()
    try:
        while True:
            statuses = queue_manager.get_all_statuses()
            await websocket.send_json(statuses)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        logger.info("dashboard websocket disconnected")
    except Exception:
        logger.exception("dashboard websocket error")
