import requests
from typing import Optional
from dotenv import load_dotenv

from system.endpoints import internal_url
import os

load_dotenv()

# 기본값이 없으면 값이 비었을 때 "None/process"로 요청이 나간다.
# 진행상황 서버는 manager/web(8006, dev 18006)이다.
PROGRESS_SERVER_URL = (
    os.getenv("PROGRESS_SERVER_URL") or internal_url("progress")
).rstrip("/")


def register_process(process_id: str, title: str) -> None:
    """
    뷰 서버에 프로세스 등록을 요청합니다.
    POST /process { title, process_id }
    """
    resp = requests.post(
        f"{PROGRESS_SERVER_URL}/process",
        json={"title": title, "process_id": process_id},
    )
    resp.raise_for_status()


def send_message(process_id, text: str) -> None:
    if not process_id:
        return

    """
    순수 문자열 메시지를 보냅니다.
    POST /notify/{process_id} { type: "message", text }
    """
    payload = {"type": "message", "text": text}
    resp = requests.post(f"{PROGRESS_SERVER_URL}/notify/{process_id}", json=payload)
    resp.raise_for_status()


def send_progress(
    process_id: str, current: int, total: int, message: Optional[str] = None
) -> None:
    """
    진행률 메시지 전송
    POST /notify/{process_id} { type: "progress", current, total, [message] }
    """
    payload = {
        "type": "progress",
        "current": current,
        "total": total,
    }
    if message:
        payload["message"] = message
    resp = requests.post(f"{PROGRESS_SERVER_URL}/notify/{process_id}", json=payload)
    resp.raise_for_status()


def send_status(process_id: str, phase: str) -> None:
    """
    중간 상태(예: 압축 시작) 전송
    POST /notify/{process_id} { type: "status", phase }
    """
    resp = requests.post(
        f"{PROGRESS_SERVER_URL}/notify/{process_id}",
        json={"type": "status", "phase": phase},
    )
    resp.raise_for_status()


def send_complete(process_id: str, download_url: str) -> None:
    """
    완료 메시지 전송
    POST /notify/{process_id} { type: "complete", url }
    """
    resp = requests.post(
        f"{PROGRESS_SERVER_URL}/notify/{process_id}",
        json={"type": "complete", "url": download_url},
    )
    resp.raise_for_status()
