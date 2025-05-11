# app/main.py

import os
import uuid
from typing import Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# 1) 앱 생성
app = FastAPI()

# 2) CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 배포 시에는 구체적 도메인으로 제한하세요
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3) 정적 파일 디렉토리 경로 계산
BASE_DIR   = os.path.dirname(__file__)           # .../manager/web/app
STATIC_DIR = os.path.join(BASE_DIR, "static")    # .../manager/web/app/static

# 4) StaticFiles 마운트
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# 5) 루트 라우트: index.html 반환
@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = os.path.join(STATIC_DIR, "index.html")
    return HTMLResponse(open(html_path, encoding="utf-8").read())


# === 프로세스 관리 ===

class ProcessInfo(BaseModel):
    title: str
    process_id: Optional[str] = Field(
        None, description="클라이언트에서 미리 생성한 프로세스 ID"
    )

# 메모리 저장소: process_id → title
processes: Dict[str, str] = {}
# process_id → WebSocket 리스트
clients: Dict[str, List[WebSocket]] = {}

class ProcessInfoOut(BaseModel):
    process_id: str
    title: str

# 1) 프로세스 메타데이터 조회
@app.get("/process/{process_id}", response_model=ProcessInfoOut)
async def get_process(process_id: str):
    if process_id not in processes:
        raise HTTPException(status_code=404, detail="Unknown process")
    return {"process_id": process_id, "title": processes[process_id]}

# 2) 프로세스 생성 엔드포인트
@app.post("/process", response_model=dict)
async def create_process(info: ProcessInfo):
    pid = info.process_id or uuid.uuid4().hex
    if pid in processes:
        raise HTTPException(status_code=400, detail="이미 존재하는 process_id 입니다")
    processes[pid] = info.title
    clients[pid] = []
    return {"process_id": pid}

# 3) WebSocket 연결 엔드포인트
@app.websocket("/ws/{process_id}")
async def ws_endpoint(ws: WebSocket, process_id: str):
    if process_id not in processes:
        await ws.close(code=1008)
        return
    await ws.accept()
    clients[process_id].append(ws)
    try:
        while True:
            # 클라이언트의 ping/pong 용도
            await ws.receive_text()
    except WebSocketDisconnect:
        clients[process_id].remove(ws)

# 4) 진행상황 알림 엔드포인트
@app.post("/notify/{process_id}")
async def notify(process_id: str, payload: dict):
    if process_id not in processes:
        raise HTTPException(status_code=404, detail="Unknown process")
    alive = []
    for ws in clients[process_id]:
        try:
            await ws.send_json(payload)
            alive.append(ws)
        except:
            # 끊어진 소켓은 제거
            pass
    clients[process_id] = alive
    return {"status": "ok"}
