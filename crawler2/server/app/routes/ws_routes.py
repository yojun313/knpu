import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

# queue_manager는 main.py에서 주입됨
queue_manager = None


def set_queue_manager(qm):
    global queue_manager
    queue_manager = qm


@router.websocket("/ws/dashboard")
async def dashboard_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            statuses = queue_manager.get_all_statuses()
            await websocket.send_json(statuses)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
