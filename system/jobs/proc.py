"""프로세스 그룹 관리 유틸(리눅스 /proc 기반). 표준 라이브러리만 쓴다 — 감독 프로세스가 가볍게 import 한다."""

import ctypes
import os
import signal
import time

_PR_SET_PDEATHSIG = 1


def set_pdeathsig(sig: int = signal.SIGTERM) -> None:
    """부모가 죽으면 이 프로세스가 sig 를 받도록 커널에 등록한다(리눅스 전용, 실패는 무시)."""
    try:
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        libc.prctl(_PR_SET_PDEATHSIG, int(sig), 0, 0, 0)
    except Exception:
        pass


def group_members(pgid: int, *, exclude_self: bool = False) -> list[int]:
    """프로세스 그룹 pgid 에 속한 살아 있는 pid 목록(좀비 제외)."""
    me = os.getpid()
    out = []
    try:
        names = os.listdir("/proc")
    except OSError:
        return out
    for name in names:
        if not name.isdigit():
            continue
        pid = int(name)
        if exclude_self and pid == me:
            continue
        try:
            with open(f"/proc/{pid}/stat", "rb") as f:
                stat = f.read().decode("utf-8", "replace")
        except OSError:
            continue
        # comm 에 공백·괄호가 들어갈 수 있어 마지막 ')' 뒤부터 나눈다
        rest = stat[stat.rfind(")") + 2 :].split()
        if len(rest) < 3:
            continue
        state, pgrp = rest[0], rest[2]
        if state in ("Z", "X"):
            continue
        if int(pgrp) == pgid:
            out.append(pid)
    return out


def cmdline(pid: int) -> str:
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            return f.read().replace(b"\0", b" ").decode("utf-8", "replace")
    except OSError:
        return ""


def signal_group(pgid: int, sig: int, *, exclude_self: bool = False) -> None:
    """그룹 전체에 시그널. exclude_self 면 자기 자신은 빼고 구성원에게 하나씩 보낸다."""
    if not exclude_self:
        try:
            os.killpg(pgid, sig)
        except (ProcessLookupError, PermissionError):
            pass
        return
    for pid in group_members(pgid, exclude_self=True):
        try:
            os.kill(pid, sig)
        except (ProcessLookupError, PermissionError):
            pass


def kill_group(pgid: int, *, grace: float = 6.0, exclude_self: bool = False) -> bool:
    """SIGTERM → grace 초 기다림 → 남아 있으면 SIGKILL. 그룹이 비면 True."""
    if not group_members(pgid, exclude_self=exclude_self):
        return True
    signal_group(pgid, signal.SIGTERM, exclude_self=exclude_self)
    deadline = time.time() + grace
    while time.time() < deadline:
        if not group_members(pgid, exclude_self=exclude_self):
            return True
        time.sleep(0.2)
    deadline = time.time() + 3
    while time.time() < deadline:
        # 그 사이 새로 fork 된 프로세스까지 잡도록 반복해서 보낸다
        signal_group(pgid, signal.SIGKILL, exclude_self=exclude_self)
        time.sleep(0.1)
        if not group_members(pgid, exclude_self=exclude_self):
            return True
    return not group_members(pgid, exclude_self=exclude_self)
