import requests
from config import MANAGER_PROGRESS_API

VIEW_SERVER = MANAGER_PROGRESS_API

def register_process(process_id: str, title: str):
    """
    뷰 서버에 프로세스 등록을 요청
    POST /process { title, process_id }
    """
    resp = requests.post(
        f"{VIEW_SERVER}/process",
        json={"title": title, "process_id": process_id}
    )
    resp.raise_for_status()

def _notify(process_id, payload):
    """
    /notify/{process_id} 로 메시지를 전송한다.
    payload 에는 최소 'type' 키가 포함되어야 함.
    실패 시 raise_for_status() 로 예외 발생.
    """
    url = f"{VIEW_SERVER}/notify/{process_id}"
    resp = requests.post(url, json=payload)
    resp.raise_for_status()

def send_message(process_id: str, text: str) -> None:
    """
    클라이언트 화면에 단순 텍스트를 표시한다.
    """
    _notify(process_id, {"type": "message", "text": text})

def send_progress(process_id: str, current: int, total: int) -> None:
    """
    current/total 로 진행률 바를 갱신한다.
    """
    _notify(process_id, {"type": "progress", "current": current, "total": total})

def send_status(process_id: str, phase: str) -> None:
    """
    단계명을 표시한다. (예: '다운로드', '변환 중' 등)
    """
    _notify(process_id, {"type": "status", "phase": phase})
