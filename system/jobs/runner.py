"""서비스별 작업 러너 — 웹 서버 안에서 도는 스레드 하나.

1초마다:
  1) 예약 시각이 된 scheduled 작업 → queued
  2) 중단 요청된 실행 중 작업 → 감독 프로세스에 SIGTERM, 시간이 지나도 그룹이 남으면 SIGKILL
  3) 끝난 감독 프로세스 거두기 → 최종 상태 확정(작업이 직접 못 남긴 경우 error/cancelled)
  4) 동시 실행 한도 안에서 queued 작업을 원자적으로 집어 새 프로세스 그룹으로 실행

웹 서버가 종료될 때(PM2 stop/restart) 실행 중인 그룹을 모두 정리하고 'interrupted' 로 남긴다.
웹 서버가 SIGKILL 로 죽으면 감독 프로세스의 PDEATHSIG 가 그룹을 정리하고, 다음 기동 때
recover() 가 남은 문서를 'interrupted' 로 바꾼다(혹시 살아남은 그룹이 있으면 여기서 죽인다).
"""

import atexit
import logging
import os
import signal
import subprocess
import sys
import threading
import time

from pymongo import ReturnDocument

from system.jobs import store
from system.jobs.proc import cmdline, group_members, kill_group, signal_group

logger = logging.getLogger("system.jobs")

_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
CANCEL_GRACE_S = 12.0  # 감독이 그룹을 정리할 시간. 지나면 러너가 직접 SIGKILL


class Runner:
    def __init__(self, service: str, entry: str, cwd: str, max_concurrent: int):
        self.service = service
        self.entry = entry
        self.cwd = cwd
        self.max_concurrent = max(1, max_concurrent)
        self.procs: dict[str, dict] = {}  # job_id -> {"proc", "pgid", "cancel_ts"}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._last_gc = 0.0

    # ------------------------------------------------------------ 수명 ---
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        try:
            store.ensure_indexes()
            self.recover()
        except Exception:
            logger.exception("[jobs] recover 실패")
        # PDEATHSIG 는 '자식을 만든 스레드'가 끝날 때도 발동하므로, 자식은 항상
        # 서버가 살아 있는 동안 계속 도는 이 스레드에서만 만든다.
        self._thread = threading.Thread(
            target=self._loop, name=f"jobs-runner-{self.service}", daemon=True
        )
        self._thread.start()
        atexit.register(self.shutdown)

    def shutdown(self) -> None:
        """서버 종료: 실행 중인 그룹을 모두 정리하고 interrupted 로 남긴다."""
        if self._stop.is_set():
            return
        self._stop.set()
        with self._lock:
            items = list(self.procs.items())
        for _job_id, info in items:
            try:
                info["proc"].send_signal(signal.SIGTERM)
            except Exception:
                pass
        deadline = time.time() + 6
        for job_id, info in items:
            pgid = info["pgid"]
            while time.time() < deadline and group_members(pgid):
                time.sleep(0.1)
            if group_members(pgid):
                kill_group(pgid, grace=0.5)
            try:
                info["proc"].wait(timeout=1)
            except Exception:
                pass
            try:
                job = store.get(job_id, {"cancel_requested": 1})
                if job and job.get("cancel_requested"):
                    store.finish(
                        job_id, "cancelled", only_from=store.RUNNING, stage="중단됨"
                    )
                else:
                    store.finish(
                        job_id,
                        "interrupted",
                        only_from=store.RUNNING,
                        stage="서버 종료로 중단됨",
                        error="서버가 재시작/종료되어 작업이 중단되었습니다. '다시 실행'으로 이어서 실행할 수 있습니다.",
                    )
            except Exception:
                pass
        with self._lock:
            self.procs.clear()

    def recover(self) -> None:
        """기동 시: 이 서버(host)에서 실행 중으로 남은 작업 정리."""
        col = store.collection()
        for job in col.find(
            {"service": self.service, "status": {"$in": list(store.RUNNING)}},
            {"host": 1, "pgid": 1, "cancel_requested": 1},
        ):
            if job.get("host") not in (None, store.HOST):
                continue  # 다른 서버에서 돌고 있는 작업은 건드리지 않는다
            pgid = job.get("pgid")
            if pgid and job["_id"] in cmdline(pgid):
                kill_group(pgid, grace=3)
            if job.get("cancel_requested"):
                store.finish(
                    job["_id"], "cancelled", only_from=store.RUNNING, stage="중단됨"
                )
            else:
                store.finish(
                    job["_id"],
                    "interrupted",
                    only_from=store.RUNNING,
                    stage="서버 재시작으로 중단됨",
                    error="서버가 재시작되어 작업이 중단되었습니다. '다시 실행'으로 이어서 실행할 수 있습니다.",
                )

    # ------------------------------------------------------------ 루프 ---
    def _loop(self) -> None:
        while not self._stop.wait(1.0):
            try:
                self.tick()
            except Exception:
                logger.exception("[jobs] runner tick 실패")
                self._stop.wait(3)

    def tick(self) -> None:
        now = time.time()
        col = store.collection()
        # 1) 예약 → 대기
        col.update_many(
            {
                "service": self.service,
                "status": "scheduled",
                "scheduled_ts": {"$lte": now},
                "cancel_requested": {"$ne": True},
            },
            {"$set": {"status": "queued", "queued_ts": now, "stage": "대기 중"}},
        )
        # 2) 중단 요청 처리
        with self._lock:
            mine = list(self.procs.items())
        if mine:
            wanted = {
                d["_id"]
                for d in col.find(
                    {"_id": {"$in": [j for j, _ in mine]}, "cancel_requested": True},
                    {"_id": 1},
                )
            }
            for job_id, info in mine:
                if job_id not in wanted:
                    continue
                if info.get("cancel_ts") is None:
                    info["cancel_ts"] = now
                    col.update_one(
                        {"_id": job_id, "status": {"$in": list(store.RUNNING)}},
                        {"$set": {"status": "cancelling", "stage": "중단하는 중…"}},
                    )
                    try:
                        info["proc"].send_signal(signal.SIGTERM)
                    except Exception:
                        pass
                elif now - info["cancel_ts"] > CANCEL_GRACE_S:
                    signal_group(info["pgid"], signal.SIGKILL)
        # 3) 끝난 프로세스 거두기
        for job_id, info in mine:
            code = info["proc"].poll()
            if code is None:
                continue
            # 감독은 끝났어도 그룹이 남아 있으면(감독이 SIGKILL 당한 경우) 마저 정리
            if group_members(info["pgid"]):
                kill_group(info["pgid"], grace=2)
            self._finalize(job_id)
            with self._lock:
                self.procs.pop(job_id, None)
        # 4) 대기 작업 시작
        while len(self.procs) < self.max_concurrent and not self._stop.is_set():
            job = col.find_one_and_update(
                {
                    "service": self.service,
                    "status": "queued",
                    "cancel_requested": {"$ne": True},
                },
                {
                    "$set": {
                        "status": "starting",
                        "stage": "프로세스 시작 중",
                        "host": store.HOST,
                    }
                },
                sort=[("queued_ts", 1), ("created_ts", 1)],
                return_document=ReturnDocument.AFTER,
            )
            if not job:
                break
            self._launch(job)
        # 대기열에 늦게 들어온 작업의 '앞에 N개' 안내
        self._update_queue_positions(col)
        if now - self._last_gc > 3600:
            self._last_gc = now
            try:
                store.gc()
            except Exception:
                pass

    def _update_queue_positions(self, col) -> None:
        queued = list(
            col.find(
                {"service": self.service, "status": "queued"},
                {"_id": 1, "stage": 1},
            ).sort([("queued_ts", 1), ("created_ts", 1)])
        )
        for i, job in enumerate(queued):
            stage = (
                f"대기 중 — 앞에 실행 중인 작업 {len(self.procs)}개, 대기 {i}개"
                if i or self.procs
                else "대기 중"
            )
            if job.get("stage") != stage:
                col.update_one(
                    {"_id": job["_id"], "status": "queued"}, {"$set": {"stage": stage}}
                )

    def _launch(self, job: dict) -> None:
        job_id = job["_id"]
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(
            p for p in (_REPO_ROOT, self.cwd, env.get("PYTHONPATH")) if p
        )
        env["PYTHONUNBUFFERED"] = "1"
        env["KNPU_JOB_ID"] = job_id
        try:
            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "system.jobs.worker",
                    "supervise",
                    job_id,
                    str(os.getpid()),
                    self.entry,
                ],
                cwd=self.cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,  # 새 세션 = 새 프로세스 그룹(pgid = 감독 pid)
                close_fds=True,
            )
        except Exception as e:
            store.finish(
                job_id,
                "error",
                only_from=("starting",),
                error=f"작업 프로세스를 시작하지 못했습니다: {e}",
                stage="실패",
            )
            return
        with self._lock:
            self.procs[job_id] = {"proc": proc, "pgid": proc.pid, "cancel_ts": None}
        store.collection().update_one(
            {"_id": job_id}, {"$set": {"pgid": proc.pid, "heartbeat_ts": time.time()}}
        )

    def _finalize(self, job_id: str) -> None:
        job = store.get(job_id)
        if not job:
            return
        if job.get("status") in store.FINISHED:
            return  # 입력 사본은 '다시 실행'용으로 남긴다(store.gc 가 14일 뒤 정리)
        if job.get("cancel_requested"):
            store.finish(job_id, "cancelled", stage="중단됨", progress=None)
            store.append_log(
                job_id,
                [
                    {
                        "t": time.time(),
                        "text": "사용자 요청으로 작업을 중단했습니다. 프로세스를 모두 정리했습니다.",
                        "level": "warn",
                    }
                ],
            )
            return
        tail = _log_tail(job_id)
        store.finish(
            job_id,
            "error",
            stage="실패",
            error="작업 프로세스가 비정상 종료되었습니다."
            + (f"\n{tail}" if tail else ""),
        )


def _log_tail(job_id: str, lines: int = 12) -> str:
    path = os.path.join(store.job_dir(job_id), "worker.log")
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - 4000))
            text = f.read().decode("utf-8", "replace")
    except OSError:
        return ""
    return "\n".join(text.strip().splitlines()[-lines:])
