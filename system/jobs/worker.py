"""분석 작업 실행 프로세스.

러너(웹 서버 안의 스레드)는 작업마다 이 모듈을 '감독' 모드로 새 세션(=새 프로세스 그룹)에서 띄운다.

  웹 서버 ─ 감독(supervise, 그룹 리더, 가벼움) ─ 실행(run, 실제 분석) ─ 풀 워커·resource_tracker …

* 감독은 표준 라이브러리만 쓰고 대부분 child.wait() 에서 쉬므로 시그널에 즉시 반응한다.
  SIGTERM/SIGINT/SIGHUP 을 받거나 웹 서버(부모)가 사라지면 그룹 전체를 SIGTERM → SIGKILL 로 정리한다.
  분석이 정상 종료돼도 남은 손자 프로세스(ProcessPoolExecutor·loky 워커 등)를 마지막에 걷어 낸다.
* 감독·실행 모두 PR_SET_PDEATHSIG 를 걸어, 웹 서버가 SIGKILL 로 죽어도 고아로 남지 않는다.
* 실행은 서비스 폴더(cwd)에서 진입 함수(예: app.services.analyze_service:run_job)를 불러 분석하고,
  system.progress 로 보내던 진행 메시지를 작업 문서의 로그로도 남긴다.
"""

import os
import signal
import subprocess
import sys
import time

_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)


# ---------------------------------------------------------------- 감독 ---


def supervise(job_id: str, parent_pid: int, entry: str) -> int:
    from system.jobs.proc import kill_group, set_pdeathsig

    set_pdeathsig(signal.SIGTERM)
    if os.getppid() != parent_pid:  # prctl 전에 부모가 이미 죽었다
        return 3

    stop: dict = {"sig": None}

    def on_signal(signum, _frame):
        stop["sig"] = signum

    for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(s, on_signal)

    from system.jobs.store import job_dir

    folder = job_dir(job_id)
    os.makedirs(folder, exist_ok=True)
    pgid = os.getpgid(0)
    with open(os.path.join(folder, "worker.log"), "ab") as log:
        child = subprocess.Popen(
            [sys.executable, "-m", "system.jobs.worker", "run", job_id, entry],
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            cwd=os.getcwd(),
            env=os.environ.copy(),
        )
        code = None
        while code is None:
            try:
                code = child.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                pass
            if code is None and (stop["sig"] or os.getppid() != parent_pid):
                break
        # 중단이든 정상 종료든 그룹에 남은 프로세스를 모두 정리한다(자기 자신 제외)
        kill_group(pgid, grace=5.0 if code is None else 2.0, exclude_self=True)
        if code is None:
            try:
                code = child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                code = -9
    try:
        with open(os.path.join(folder, "exit_code"), "w") as f:
            f.write(str(code))
    except OSError:
        pass
    return 0


# ---------------------------------------------------------------- 실행 ---


from system.jobs.errors import JobError  # noqa: E402,F401  (예전 import 경로 호환)


class JobContext:
    """진입 함수에 넘겨지는 작업 정보 + 진행 기록 도구."""

    def __init__(self, job: dict):
        import collections
        import threading

        from system.jobs import store

        self.job = job
        self.id = job["_id"]
        self.uid = job["uid"]
        self.params = dict(job.get("params") or {})
        self.title = job.get("title") or ""
        self.input_path = store.input_path(job)
        self.input_filename = (job.get("input") or {}).get("filename")
        self._store = store
        self._lock = threading.Lock()
        self._lines: list[dict] = []
        self._fields: dict = {}
        self._recent = collections.deque(maxlen=200)  # 진행 서버 에코 중복 제거용

    # 분석 코드가 부르는 API
    def log(self, text: str, level: str = "info", *, stage: bool = True) -> None:
        text = str(text or "").rstrip()
        if not text:
            return
        with self._lock:
            self._lines.append({"t": time.time(), "text": text[:2000], "level": level})
            if stage and level != "err":
                self._fields["stage"] = text.splitlines()[0][:200]

    def progress(self, current, total, message: str | None = None) -> None:
        try:
            cur, tot = float(current), float(total)
        except (TypeError, ValueError):
            return
        with self._lock:
            self._fields["progress"] = {"current": cur, "total": tot}
        if message:
            self.log(message)

    def stage(self, text: str) -> None:
        with self._lock:
            self._fields["stage"] = str(text)[:200]

    # 내부
    def remember(self, text: str) -> None:
        self._recent.append(str(text or "").rstrip())

    def is_echo(self, text: str) -> bool:
        text = str(text or "").rstrip()
        try:
            self._recent.remove(text)
            return True
        except ValueError:
            return False

    def flush(self) -> None:
        with self._lock:
            lines, self._lines = self._lines, []
            fields, self._fields = self._fields, {}
        fields["heartbeat_ts"] = time.time()
        try:
            self._store.append_log(self.id, lines, fields)
        except Exception as e:  # DB 일시 오류 — 다음 주기에 다시 시도
            print(f"[jobs] flush 실패: {e}", file=sys.stderr, flush=True)
            with self._lock:
                self._lines = lines + self._lines
                self._fields = {**fields, **self._fields}


def _patch_progress(ctx: JobContext) -> None:
    """system.progress 의 함수들을 감싸 작업 로그에도 남긴다(분석 모듈 import 전에 호출)."""
    import system.progress as P

    orig_message, orig_progress, orig_status = (
        P.send_message,
        P.send_progress,
        P.send_status,
    )

    def send_message(process_id, text):
        if process_id == ctx.id:
            ctx.log(text)
            ctx.remember(text)
        orig_message(process_id, text)

    def send_progress(process_id, current, total, message=None):
        if process_id == ctx.id:
            ctx.progress(current, total, message)
        try:
            orig_progress(process_id, current, total, message)
        except Exception:
            pass

    def send_status(process_id, phase):
        if process_id == ctx.id:
            ctx.stage(phase)
        try:
            orig_status(process_id, phase)
        except Exception:
            pass

    P.send_message, P.send_progress, P.send_status = (
        send_message,
        send_progress,
        send_status,
    )


def _register_progress(ctx: JobContext, title: str) -> str | None:
    """진행 서버(manager/web)에 같은 id 로 등록 — GPU 서버처럼 그쪽으로만 메시지를 보내는
    외부 단계의 진행도 받아 적고, 매니저 화면과의 호환도 유지한다."""
    import requests

    from system.progress import PROGRESS_SERVER_URL

    try:
        requests.post(
            f"{PROGRESS_SERVER_URL}/process",
            json={"title": title, "process_id": ctx.id},
            timeout=5,
        ).raise_for_status()
    except Exception as e:
        print(
            f"[jobs] 진행 서버 등록 실패(계속 진행): {e}", file=sys.stderr, flush=True
        )
        return None
    return (
        PROGRESS_SERVER_URL.replace("http://", "ws://", 1).replace(
            "https://", "wss://", 1
        )
        + f"/ws/{ctx.id}"
    )


def _mirror_progress(ctx: JobContext, ws_url: str, stop) -> None:
    """진행 서버 WebSocket 을 구독해 이 프로세스가 직접 보내지 않은 메시지
    (GPU 서버, spawn 된 풀 워커 등)를 작업 로그에 옮겨 적는다."""
    import json

    try:
        from websockets.sync.client import connect
    except Exception:
        return
    while not stop.is_set():
        try:
            with connect(ws_url, open_timeout=5, close_timeout=1) as ws:
                while not stop.is_set():
                    try:
                        raw = ws.recv(timeout=1)
                    except TimeoutError:
                        continue
                    try:
                        msg = json.loads(raw)
                    except ValueError:
                        continue
                    if msg.get("type") == "message" and msg.get("text"):
                        if not ctx.is_echo(msg["text"]):
                            ctx.log(msg["text"])
                    elif msg.get("type") == "progress":
                        ctx.progress(
                            msg.get("current"), msg.get("total"), msg.get("message")
                        )
        except Exception:
            if stop.wait(3):
                return


def run(job_id: str, entry: str) -> int:
    import importlib
    import threading
    import traceback

    from system.jobs.proc import set_pdeathsig

    set_pdeathsig(signal.SIGTERM)
    for p in (os.getcwd(), _REPO_ROOT):
        if p not in sys.path:
            sys.path.insert(0, p)

    from system.jobs import store

    job = store.get(job_id)
    if not job:
        print(f"[jobs] 작업 {job_id} 없음", file=sys.stderr)
        return 2
    if job.get("cancel_requested"):
        return 0
    store.collection().update_one(
        {"_id": job_id, "status": "starting"},
        {
            "$set": {
                "status": "running",
                "started_ts": time.time(),
                "heartbeat_ts": time.time(),
                "stage": "분석 준비 중",
                "worker_pid": os.getpid(),
            }
        },
    )
    ctx = JobContext(job)
    _patch_progress(ctx)

    stop = threading.Event()

    def flusher():
        while not stop.wait(1.0):
            ctx.flush()

    threading.Thread(target=flusher, daemon=True).start()
    ws_url = _register_progress(ctx, job.get("kind_label") or "분석")
    if ws_url:
        threading.Thread(
            target=_mirror_progress, args=(ctx, ws_url, stop), daemon=True
        ).start()
        time.sleep(0.3)  # 구독이 붙은 뒤 분석을 시작해야 첫 메시지를 놓치지 않는다

    ctx.log(f"작업 시작 — {job.get('kind_label') or job.get('kind')}: {ctx.title}")
    status, fields = "done", {}
    try:
        mod_name, fn_name = entry.split(":", 1)
        fn = getattr(importlib.import_module(mod_name), fn_name)
        result = fn(ctx) or {}
        fields = {
            "result": result,
            "stage": "완료",
            "summary": result.get("summary") if isinstance(result, dict) else None,
        }
        ctx.log("완료! 결과를 프로젝트로 저장했습니다.", level="ok", stage=False)
    except JobError as e:
        status, fields = "error", {"error": str(e), "stage": "실패"}
        ctx.log(f"오류: {e}", level="err")
    except Exception as e:
        traceback.print_exc()
        msg = str(e) or type(e).__name__
        status, fields = "error", {"error": msg, "stage": "실패"}
        ctx.log(f"오류: {msg}", level="err")
    finally:
        stop.set()
        ctx.flush()
    store.finish(job_id, status, only_from=("running", "starting"), **fields)
    return 0


def main(argv: list[str]) -> int:
    if len(argv) >= 4 and argv[0] == "supervise":
        return supervise(argv[1], int(argv[2]), argv[3])
    if len(argv) >= 3 and argv[0] == "run":
        return run(argv[1], argv[2])
    print("usage: python -m system.jobs.worker supervise <job_id> <parent_pid> <entry>")
    return 2


if __name__ == "__main__":
    if _REPO_ROOT not in sys.path:
        sys.path.insert(0, _REPO_ROOT)
    sys.exit(main(sys.argv[1:]))
