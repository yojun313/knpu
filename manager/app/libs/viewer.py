import os
import sys
import shutil
import subprocess
import requests
import tempfile
from config import MANAGER_PROGRESS_API

VIEW_SERVER = MANAGER_PROGRESS_API

'''
    사용법
    register_process(pid, f"Crawl DB Save")
    viewer = open_viewer(pid)
    close_viewer(viewer)
'''

def register_process(process_id: str, title: str):
    """
    뷰 서버에 프로세스 등록을 요청합니다.
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

# ─────────────────────────────────────────────────────────────
# 1) 일반 텍스트 메시지
def send_message(process_id: str, text: str) -> None:
    """
    클라이언트 화면에 단순 텍스트를 표시한다.
    """
    _notify(process_id, {"type": "message", "text": text})

# 2) 진행률 업데이트
def send_progress(process_id: str, current: int, total: int) -> None:
    """
    current/total 로 진행률 바를 갱신한다.
    """
    _notify(process_id, {"type": "progress", "current": current, "total": total})

# 3) 단계(phase) 상태 업데이트
def send_status(process_id: str, phase: str) -> None:
    """
    단계명을 표시한다. (예: '다운로드', '변환 중' 등)
    """
    _notify(process_id, {"type": "status", "phase": phase})

def open_viewer(pid: str, width: int=800, height: int=400):
    """
    --user-data-dir 로 완전 분리된 프로필을 사용해 Chrome을 띄우고,
    Popen 객체에 프로필 디렉터리 경로를 붙여 반환합니다.
    """
    url = f"{VIEW_SERVER}/?pid={pid}"
    profile_dir = tempfile.mkdtemp(prefix="chrome-profile-")

    # 실행할 Chrome 경로 결정
    if sys.platform.startswith("win"):
        chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    elif sys.platform.startswith("darwin"):
        chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    else:
        for name in ("google-chrome","chrome","chromium-browser","chromium"):
            path = shutil.which(name)
            if path:
                chrome = path
                break
        else:
            # fallback: 기본 브라우저
            import webbrowser
            webbrowser.open(url)
            return None

    # Chrome이 없으면 빠져나옴
    if not os.path.exists(chrome):
        import webbrowser
        webbrowser.open(url)
        return None

    # 분리된 프로필 + 앱 모드
    proc = subprocess.Popen([
        chrome,
        f"--user-data-dir={profile_dir}",
        f"--app={url}",
        f"--window-size={width},{height}"
    ])
    # 나중에 닫을 때 지워야 할 프로필 디렉터리 저장
    proc.profile_dir = profile_dir
    return proc

def close_viewer(proc):
    """
    terminate → wait → kill 순서로 창을 닫고,
    임시 프로필도 삭제합니다.
    """
    if not proc:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    # 프로필 디렉터리 삭제
    shutil.rmtree(proc.profile_dir, ignore_errors=True)