import subprocess

REPO_PATH = "/home/lab/knpu"

STATUS_LABELS = {
    "M": "수정",
    "A": "추가",
    "D": "삭제",
    "R": "이름변경",
    "C": "복사",
    "U": "충돌",
    "?": "새 파일",
}


class GitError(Exception):
    pass


def _run(args: list[str], timeout: int = 30) -> dict:
    result = subprocess.run(
        ["git", "-C", REPO_PATH] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return {
        "ok": result.returncode == 0,
        # rstrip만 한다 — porcelain status처럼 첫 줄 맨 앞 공백이 상태 코드의 일부라
        # strip()을 쓰면 첫 줄만 한 칸씩 밀려서 파싱이 깨진다.
        "stdout": result.stdout.rstrip(),
        "stderr": result.stderr.rstrip(),
        "returncode": result.returncode,
    }


def get_current_branch() -> str:
    r = _run(["rev-parse", "--abbrev-ref", "HEAD"])
    return r["stdout"] if r["ok"] else "HEAD"


def get_local_branches() -> list[str]:
    r = _run(["branch", "--format=%(refname:short)"])
    if not r["ok"]:
        return []
    return [b.strip() for b in r["stdout"].splitlines() if b.strip()]


def get_remote_branches() -> list[str]:
    r = _run(["branch", "-r", "--format=%(refname:short)"])
    if not r["ok"]:
        return []
    branches = []
    for line in r["stdout"].splitlines():
        line = line.strip()
        if not line or "->" in line or not line.startswith("origin/"):
            continue
        branches.append(line[len("origin/") :])
    return branches


def get_uncommitted_files() -> list[dict]:
    r = _run(["status", "--porcelain=v1"])
    if not r["ok"]:
        return []
    files = []
    for line in r["stdout"].splitlines():
        if not line:
            continue
        code = line[:2].strip()
        path = line[3:]
        label_key = code[0] if code and code[0] != "?" else "?"
        files.append({"code": code or "?", "path": path, "label": STATUS_LABELS.get(label_key, code or "?")})
    return files


def get_ahead_behind(branch: str, remote_branches: list[str]) -> dict:
    if branch not in remote_branches:
        return {"ahead": 0, "behind": 0, "tracking": False}
    r = _run(["rev-list", "--left-right", "--count", f"origin/{branch}...{branch}"])
    if not r["ok"] or not r["stdout"]:
        return {"ahead": 0, "behind": 0, "tracking": False}
    parts = r["stdout"].split()
    if len(parts) != 2:
        return {"ahead": 0, "behind": 0, "tracking": False}
    behind, ahead = int(parts[0]), int(parts[1])
    return {"ahead": ahead, "behind": behind, "tracking": True}


def get_recent_commits(limit: int = 15) -> list[dict]:
    fmt = "%H\x1f%h\x1f%an\x1f%ad\x1f%s"
    r = _run(["log", f"-{limit}", f"--pretty=format:{fmt}", "--date=format:%Y-%m-%d %H:%M"])
    commits = []
    if r["ok"]:
        for line in r["stdout"].splitlines():
            parts = line.split("\x1f")
            if len(parts) == 5:
                commits.append(
                    {
                        "hash": parts[0],
                        "short_hash": parts[1],
                        "author": parts[2],
                        "date": parts[3],
                        "message": parts[4],
                    }
                )
    return commits


def get_status() -> dict:
    branch = get_current_branch()
    remote_branches = get_remote_branches()
    ahead_behind = get_ahead_behind(branch, remote_branches)

    return {
        "repo_path": REPO_PATH,
        "branch": branch,
        "local_branches": get_local_branches(),
        "remote_branches": remote_branches,
        "ahead": ahead_behind["ahead"],
        "behind": ahead_behind["behind"],
        "tracking": ahead_behind["tracking"],
        "dirty_files": get_uncommitted_files(),
        "recent_commits": get_recent_commits(15),
    }


def fetch_all() -> dict:
    r = _run(["fetch", "--all", "--prune"], timeout=60)
    if not r["ok"]:
        raise GitError(r["stderr"] or "fetch 실패")
    return r


def commit_all(message: str) -> dict:
    message = (message or "").strip()
    if not message:
        raise GitError("커밋 메시지를 입력해주세요")

    add_result = _run(["add", "-A"])
    if not add_result["ok"]:
        raise GitError(add_result["stderr"] or "변경사항을 스테이징하지 못했습니다")

    diff_check = _run(["diff", "--cached", "--quiet"])
    if diff_check["returncode"] == 0:
        raise GitError("커밋할 변경사항이 없습니다")

    commit_result = _run(["commit", "-m", message])
    if not commit_result["ok"]:
        raise GitError(commit_result["stderr"] or commit_result["stdout"] or "커밋 실패")
    return commit_result


def push_current() -> dict:
    branch = get_current_branch()
    upstream_check = _run(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    args = ["push", "origin", branch] if upstream_check["ok"] else ["push", "-u", "origin", branch]
    result = _run(args, timeout=60)
    if not result["ok"]:
        raise GitError(result["stderr"] or result["stdout"] or "push 실패")
    return result


def pull_current() -> dict:
    branch = get_current_branch()
    result = _run(["pull", "origin", branch], timeout=60)
    if not result["ok"]:
        raise GitError(result["stderr"] or result["stdout"] or "pull 실패 (충돌이 있을 수 있습니다)")
    return result


def merge_preview(source_branch: str) -> dict:
    remote_branches = get_remote_branches()
    if source_branch not in remote_branches:
        raise GitError(f"알 수 없는 브랜치: {source_branch}")

    fetch_all()

    r = _run(["log", f"main..origin/{source_branch}", "--pretty=format:%h\x1f%an\x1f%s", "-30"])
    commits = []
    if r["ok"] and r["stdout"]:
        for line in r["stdout"].splitlines():
            parts = line.split("\x1f")
            if len(parts) == 3:
                commits.append({"short_hash": parts[0], "author": parts[1], "message": parts[2]})
    return {"branch": source_branch, "commits": commits, "count": len(commits)}


def merge_into_main(source_branch: str) -> dict:
    remote_branches = get_remote_branches()
    if source_branch not in remote_branches:
        raise GitError(f"알 수 없는 브랜치: {source_branch}")
    if source_branch == "main":
        raise GitError("main은 병합 대상이 될 수 없습니다")

    if get_uncommitted_files():
        raise GitError("커밋되지 않은 변경사항이 있습니다. 먼저 커밋하거나 정리해주세요.")

    fetch_all()

    checkout = _run(["checkout", "main"])
    if not checkout["ok"]:
        raise GitError(checkout["stderr"] or "main 브랜치로 전환하지 못했습니다")

    pull_main = _run(["pull", "origin", "main"], timeout=60)
    if not pull_main["ok"]:
        raise GitError(pull_main["stderr"] or "main을 최신 상태로 가져오지 못했습니다")

    merge_result = _run(
        ["merge", "--no-ff", f"origin/{source_branch}", "-m", f"Merge branch '{source_branch}' into main"],
        timeout=60,
    )
    if not merge_result["ok"]:
        # 충돌 등으로 실패하면 즉시 되돌린다 — 모바일 UI에서는 사용자가 충돌을 직접
        # 해결할 수 없으므로 절대 병합 충돌 상태로 저장소를 남겨두지 않는다.
        _run(["merge", "--abort"])
        raise GitError(
            "병합에 실패해 자동으로 되돌렸습니다 (충돌 가능성).\n"
            + (merge_result["stderr"] or merge_result["stdout"])
        )

    return {
        "message": f"'{source_branch}' 브랜치를 main에 병합했습니다. 아직 push되지 않았습니다 — 확인 후 Push를 눌러주세요.",
        "detail": merge_result["stdout"],
    }


def get_file_diff(path: str) -> str:
    dirty_paths = {f["path"] for f in get_uncommitted_files()}
    if path not in dirty_paths:
        raise GitError("변경된 파일 목록에 없는 경로입니다")
    r = _run(["diff", "HEAD", "--", path])
    return r["stdout"] or "(변경 내용을 표시할 수 없습니다 — 바이너리 파일일 수 있습니다)"
