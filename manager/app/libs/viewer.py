import requests
from config import MANAGER_PROGRESS_API

VIEW_SERVER = MANAGER_PROGRESS_API


def register_process(process_id: str, title: str):
    resp = requests.post(
        f"{VIEW_SERVER}/process", json={"title": title, "process_id": process_id}
    )
    resp.raise_for_status()


def _notify(process_id, payload):
    url = f"{VIEW_SERVER}/notify/{process_id}"
    resp = requests.post(url, json=payload)
    resp.raise_for_status()


def send_message(process_id: str, text: str) -> None:
    _notify(process_id, {"type": "message", "text": text})


def send_progress(process_id: str, current: int, total: int) -> None:
    _notify(process_id, {"type": "progress", "current": current, "total": total})


def send_status(process_id: str, phase: str) -> None:
    _notify(process_id, {"type": "status", "phase": phase})
