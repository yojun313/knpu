import os
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

PROGRESS_SERVER_URL = os.getenv("PROGRESS_SERVER_URL")


def register_process(process_id: str, title: str) -> None:
    resp = requests.post(
        f"{PROGRESS_SERVER_URL}/process",
        json={"title": title, "process_id": process_id},
    )
    resp.raise_for_status()


def send_message(process_id: str, text: str) -> None:
    if not process_id:
        return

    payload = {"type": "message", "text": text}
    try:
        requests.post(
            f"{PROGRESS_SERVER_URL}/notify/{process_id}", json=payload, timeout=10
        )
    except requests.RequestException:
        pass


def send_progress(
    process_id: str, current: int, total: int, message: Optional[str] = None
) -> None:
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
    resp = requests.post(
        f"{PROGRESS_SERVER_URL}/notify/{process_id}",
        json={"type": "status", "phase": phase},
    )
    resp.raise_for_status()


def send_complete(process_id: str, download_url: str) -> None:
    resp = requests.post(
        f"{PROGRESS_SERVER_URL}/notify/{process_id}",
        json={"type": "complete", "url": download_url},
    )
    resp.raise_for_status()
