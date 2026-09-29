import hashlib
import os
import re
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GitRepository:
    id: str
    name: str
    path: Path


STATUS_NAMES = {
    "M": "수정됨",
    "T": "형식 변경",
    "A": "추가됨",
    "D": "삭제됨",
    "R": "이름 변경",
    "C": "복사됨",
    "U": "충돌",
    "?": "추적 안 됨",
    "!": "무시됨",
}
CONFLICT_CODES = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}
COMMIT_HASH = re.compile(r"^[0-9a-fA-F]{7,40}$")
STASH_REF = re.compile(r"^stash@\{\d{1,4}\}$")
CREDENTIALS_IN_URL = re.compile(r"(\w+://)[^/@\s]+@")
MAX_DIFF_BYTES = 400_000
MAX_CHANGES = 2000


class GitService:
    """설정된 위치에서 찾은 저장소만 읽고 조작한다 (UnivDash 의 Git 관리에서 옮겨 옴)."""

    COMMAND_TIMEOUT_SECONDS = 120
    ACTIONS = {
        "fetch",
        "pull",
        "push",
        "stage",
        "unstage",
        "discard",
        "commit",
        "checkout",
        "create_branch",
        "delete_branch",
        "merge",
        "abort_operation",
        "stash",
        "stash_apply",
        "stash_pop",
        "stash_drop",
        "undo_commit",
        "revert",
    }
    _repository_locks: dict[str, threading.Lock] = {}
    _locks_guard = threading.Lock()

    @classmethod
    def _git_path(cls) -> str | None:
        return shutil.which("git")

    @classmethod
    def _run(
        cls,
        repository: Path,
        *args: str,
        timeout: int | None = None,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        git_path = cls._git_path()
        if not git_path:
            raise RuntimeError("Git 실행 파일을 찾을 수 없습니다.")

        environment = os.environ.copy()
        environment["GIT_TERMINAL_PROMPT"] = "0"
        environment["GIT_OPTIONAL_LOCKS"] = (
            "0"
            if args
            and args[0] in {"status", "log", "branch", "for-each-ref", "diff", "show"}
            else "1"
        )
        # 사용자 입력 경로가 glob/매직 pathspec 으로 해석되지 않게 한다.
        environment["GIT_LITERAL_PATHSPECS"] = "1"
        # 편집기를 띄우는 명령이 서버에서 멈추지 않게 한다.
        environment["GIT_EDITOR"] = "true"
        environment["GIT_MERGE_AUTOEDIT"] = "no"
        environment["LC_ALL"] = "C"
        result = subprocess.run(
            [git_path, "-c", "color.ui=false", "-c", "core.quotepath=false", *args],
            cwd=repository,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout or cls.COMMAND_TIMEOUT_SECONDS,
            env=environment,
            check=False,
        )
        if check and result.returncode != 0:
            raise RuntimeError(
                (result.stderr or result.stdout).strip() or "Git 명령이 실패했습니다."
            )
        return result

    @staticmethod
    def _configured_paths(variable: str) -> list[Path]:
        value = os.getenv(variable, "").strip()
        if not value:
            return []
        return [
            Path(item).expanduser() for item in value.split(os.pathsep) if item.strip()
        ]

    @classmethod
    def _candidate_paths(cls) -> list[Path]:
        explicit = cls._configured_paths("GIT_REPOSITORIES")
        roots = cls._configured_paths("GIT_REPOSITORY_ROOTS")
        if not explicit and not roots:
            # 기본: knpu 저장소 자신 + 그 옆(같은 상위 폴더)에 있는 저장소들.
            from app.paths import KNPU_ROOT

            explicit = [KNPU_ROOT]
            roots = [KNPU_ROOT.parent]

        candidates = list(explicit)
        for root in roots:
            try:
                resolved_root = root.resolve()
                candidates.append(resolved_root)
                candidates.extend(
                    path for path in resolved_root.iterdir() if path.is_dir()
                )
            except (OSError, RuntimeError):
                continue
        return candidates

    @staticmethod
    def _mask(text: str) -> str:
        return CREDENTIALS_IN_URL.sub(r"\1***@", text or "")

    # ── 저장소 목록 ─────────────────────────────────────────────────────
    @classmethod
    def list_repositories(cls, include_status: bool = False) -> list[dict]:
        if not cls._git_path():
            return []

        repositories: list[GitRepository] = []
        seen: set[Path] = set()
        for candidate in cls._candidate_paths():
            try:
                path = candidate.resolve()
                if path in seen or not path.is_dir():
                    continue
                result = cls._run(path, "rev-parse", "--show-toplevel", timeout=10)
                if result.returncode != 0:
                    continue
                top_level = Path(result.stdout.strip()).resolve()
                if top_level in seen:
                    continue
                seen.add(top_level)
                repository_id = hashlib.sha256(
                    str(top_level).encode("utf-8")
                ).hexdigest()[:16]
                repositories.append(
                    GitRepository(repository_id, top_level.name, top_level)
                )
            except (OSError, RuntimeError, subprocess.SubprocessError):
                continue

        repositories.sort(key=lambda repository: repository.name.casefold())
        items = [
            {"id": repository.id, "name": repository.name, "path": str(repository.path)}
            for repository in repositories
        ]
        if include_status and items:
            with ThreadPoolExecutor(max_workers=8) as pool:
                statuses = list(
                    pool.map(lambda item: cls._quick_status(Path(item["path"])), items)
                )
            for item, status in zip(items, statuses):
                item["status"] = status
        return items

    @classmethod
    def _quick_status(cls, path: Path) -> dict[str, Any] | None:
        """목록 표시용 요약: 브랜치, 변경 수, ahead/behind."""
        try:
            result = cls._run(
                path, "status", "--porcelain=v2", "--branch", "-z", timeout=10
            )
        except (subprocess.SubprocessError, OSError, RuntimeError):
            return None
        if result.returncode != 0:
            return None
        branch = None
        ahead = behind = changes = conflicts = 0
        has_upstream = False
        entries = result.stdout.split("\0")
        index = 0
        while index < len(entries):
            entry = entries[index]
            index += 1
            if not entry:
                continue
            if entry.startswith("# branch.head "):
                branch = entry[len("# branch.head ") :]
            elif entry.startswith("# branch.upstream "):
                has_upstream = True
            elif entry.startswith("# branch.ab "):
                parts = entry.split()
                if len(parts) == 4:
                    ahead = abs(int(parts[2]))
                    behind = abs(int(parts[3]))
            elif entry.startswith("#"):
                continue
            else:
                changes += 1
                if entry.startswith("u "):
                    conflicts += 1
                if entry.startswith("2 "):
                    index += 1  # 이름 변경 항목은 원래 경로가 한 칸 더 붙는다.
        # 정렬(최근 커밋순)용 마지막 커밋 시각 (커밋이 없으면 0)
        last_commit = 0
        try:
            log = cls._run(path, "log", "-1", "--format=%ct", timeout=10)
            if log.returncode == 0 and log.stdout.strip().isdigit():
                last_commit = int(log.stdout.strip())
        except (subprocess.SubprocessError, OSError, RuntimeError):
            pass
        return {
            "branch": None if branch == "(detached)" else branch,
            "changes": changes,
            "conflicts": conflicts,
            "ahead": ahead,
            "behind": behind,
            "upstream": has_upstream,
            "last_commit": last_commit,
        }

    @classmethod
    def _get_repository(cls, repository_id: str) -> GitRepository:
        for item in cls.list_repositories():
            if item["id"] == repository_id:
                return GitRepository(item["id"], item["name"], Path(item["path"]))
        raise KeyError("등록되지 않은 Git 저장소입니다.")

    @classmethod
    def _text(cls, repository: Path, *args: str, default: str = "") -> str:
        result = cls._run(repository, *args, timeout=20)
        return result.stdout.strip() if result.returncode == 0 else default

    # ── 상세 정보 ───────────────────────────────────────────────────────
    @classmethod
    def _changes(cls, path: Path) -> list[dict[str, Any]]:
        result = cls._run(path, "status", "--porcelain=v1", "-z", "-uall", timeout=30)
        if result.returncode != 0:
            return []
        entries = result.stdout.split("\0")
        changes = []
        index = 0
        while index < len(entries) and len(changes) < MAX_CHANGES:
            entry = entries[index]
            index += 1
            if len(entry) < 4:
                continue
            code = entry[:2]
            file_path = entry[3:]
            original_path = None
            if code[0] in {"R", "C"} or code[1] in {"R", "C"}:
                original_path = entries[index] if index < len(entries) else None
                index += 1
            index_state, worktree_state = code[0], code[1]
            untracked = code == "??"
            conflict = code in CONFLICT_CODES
            if conflict:
                label_code = "U"
            elif untracked:
                label_code = "?"
            else:
                label_code = worktree_state if worktree_state != " " else index_state
            changes.append(
                {
                    "code": code,
                    "state": STATUS_NAMES.get(label_code, "변경됨"),
                    "path": file_path,
                    "original_path": original_path,
                    "staged": not untracked
                    and not conflict
                    and index_state not in {" ", "?", "!"},
                    "unstaged": untracked or conflict or worktree_state != " ",
                    "untracked": untracked,
                    "conflict": conflict,
                    "index_state": index_state,
                    "worktree_state": worktree_state,
                }
            )
        return changes

    @classmethod
    def _operation(cls, path: Path) -> str | None:
        """진행 중인 merge/rebase/cherry-pick/revert 를 알아낸다."""
        checks = (
            ("MERGE_HEAD", "merge"),
            ("rebase-merge", "rebase"),
            ("rebase-apply", "rebase"),
            ("CHERRY_PICK_HEAD", "cherry-pick"),
            ("REVERT_HEAD", "revert"),
        )
        git_dir = cls._text(path, "rev-parse", "--absolute-git-dir")
        if not git_dir:
            return None
        for name, operation in checks:
            if (Path(git_dir) / name).exists():
                return operation
        return None

    @classmethod
    def _has_head(cls, path: Path) -> bool:
        return (
            cls._run(path, "rev-parse", "--verify", "-q", "HEAD", timeout=10).returncode
            == 0
        )

    @classmethod
    def _branches(cls, path: Path, current: str) -> list[dict[str, Any]]:
        rows = cls._text(
            path,
            "for-each-ref",
            "--sort=-committerdate",
            "--format=%(refname)%1f%(refname:short)%1f%(objectname:short)%1f%(upstream:short)"
            "%1f%(upstream:track)%1f%(committerdate:iso-strict)%1f%(contents:subject)",
            "refs/heads",
            "refs/remotes",
        ).splitlines()
        branches = []
        for row in rows:
            parts = row.split("\x1f")
            if len(parts) < 7 or parts[0].endswith("/HEAD"):
                continue
            remote = parts[0].startswith("refs/remotes/")
            track = parts[4]
            ahead = behind = 0
            match = re.search(r"ahead (\d+)", track)
            if match:
                ahead = int(match.group(1))
            match = re.search(r"behind (\d+)", track)
            if match:
                behind = int(match.group(1))
            branches.append(
                {
                    "name": parts[1],
                    "hash": parts[2],
                    "upstream": parts[3],
                    "gone": "gone" in track,
                    "ahead": ahead,
                    "behind": behind,
                    "date": parts[5],
                    "subject": parts[6],
                    "current": not remote and parts[1] == current,
                    "remote": remote,
                }
            )
        branches.sort(key=lambda branch: (branch["remote"], not branch["current"]))
        return branches

    @classmethod
    def _stashes(cls, path: Path) -> list[dict[str, str]]:
        rows = cls._text(
            path, "stash", "list", "--format=%gd%x1f%gs%x1f%cI"
        ).splitlines()
        stashes = []
        for row in rows:
            parts = row.split("\x1f")
            if len(parts) == 3:
                stashes.append({"ref": parts[0], "message": parts[1], "date": parts[2]})
        return stashes

    @classmethod
    def get_repository_detail(cls, repository_id: str) -> dict:
        repository = cls._get_repository(repository_id)
        path = repository.path

        branch = cls._text(path, "branch", "--show-current")
        head = cls._text(path, "rev-parse", "--short", "HEAD", default="—")
        detached = not branch
        if detached:
            branch = f"detached@{head}"

        changes = cls._changes(path)

        ahead = behind = 0
        upstream = cls._text(path, "rev-parse", "--abbrev-ref", "@{upstream}")
        if upstream:
            counts = cls._text(
                path, "rev-list", "--left-right", "--count", f"HEAD...{upstream}"
            ).split()
            if len(counts) == 2:
                ahead, behind = (int(value) for value in counts)

        commit_rows = cls._text(
            path,
            "log",
            "-80",
            "--date=iso-strict",
            "--pretty=format:%H%x1f%h%x1f%an%x1f%aI%x1f%D%x1f%P%x1f%s",
        ).splitlines()
        commits = []
        for row in commit_rows:
            parts = row.split("\x1f", 6)
            if len(parts) == 7:
                commits.append(
                    {
                        "hash": parts[0],
                        "short_hash": parts[1],
                        "subject": parts[6],
                        "author": parts[2],
                        "date": parts[3],
                        "refs": [
                            ref.strip() for ref in parts[4].split(",") if ref.strip()
                        ],
                        "merge": len(parts[5].split()) > 1,
                        "pushed": False,
                    }
                )
        # upstream 에 없는(아직 푸시하지 않은) 커밋 표시
        if upstream and ahead:
            unpushed = set(
                cls._text(path, "rev-list", f"{upstream}..HEAD", "-n", "200").split()
            )
            for commit in commits:
                commit["pushed"] = commit["hash"] not in unpushed
        elif upstream:
            for commit in commits:
                commit["pushed"] = True

        remotes = []
        for line in cls._text(path, "remote", "-v").splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[2] == "(fetch)":
                remotes.append({"name": parts[0], "url": cls._mask(parts[1])})

        git_dir = cls._text(path, "rev-parse", "--absolute-git-dir")
        last_fetch = None
        if git_dir:
            try:
                last_fetch = datetime.fromtimestamp(
                    (Path(git_dir) / "FETCH_HEAD").stat().st_mtime, tz=UTC
                ).isoformat()
            except OSError:
                last_fetch = None

        return {
            "id": repository.id,
            "name": repository.name,
            "path": str(path),
            "branch": branch,
            "detached": detached,
            "head": head,
            "has_head": head != "—",
            "remote": cls._mask(
                cls._text(path, "config", "--get", "remote.origin.url")
            ),
            "remotes": remotes,
            "upstream": upstream,
            "ahead": ahead,
            "behind": behind,
            "last_fetch": last_fetch,
            "operation": cls._operation(path),
            "dirty": bool(changes),
            "changes": changes,
            "counts": {
                "staged": sum(1 for change in changes if change["staged"]),
                "unstaged": sum(
                    1
                    for change in changes
                    if change["unstaged"] and not change["untracked"]
                ),
                "untracked": sum(1 for change in changes if change["untracked"]),
                "conflicts": sum(1 for change in changes if change["conflict"]),
            },
            "commits": commits,
            "branches": cls._branches(path, "" if detached else branch),
            "stashes": cls._stashes(path),
            "user": {
                "name": cls._text(path, "config", "user.name"),
                "email": cls._text(path, "config", "user.email"),
            },
        }

    @staticmethod
    def _limit(text: str) -> tuple[str, bool]:
        encoded = text.encode("utf-8", errors="replace")
        if len(encoded) <= MAX_DIFF_BYTES:
            return text, False
        return encoded[:MAX_DIFF_BYTES].decode("utf-8", errors="ignore"), True

    @classmethod
    def get_diff(cls, repository_id: str, file_path: str, staged: bool = False) -> dict:
        repository = cls._get_repository(repository_id)
        change = next(
            (
                item
                for item in cls._changes(repository.path)
                if item["path"] == file_path
            ),
            None,
        )
        if change is None:
            raise KeyError("변경 목록에 없는 파일입니다.")

        if change["untracked"]:
            args = ["diff", "--no-index", "--", os.devnull, file_path]
        elif staged:
            args = ["diff", "--cached", "--find-renames", "--", file_path]
            if change["original_path"]:
                args.append(change["original_path"])
        else:
            args = ["diff", "--find-renames", "--", file_path]
        result = cls._run(repository.path, *args, timeout=30)
        text, truncated = cls._limit(result.stdout)
        return {
            "path": file_path,
            "staged": staged,
            "diff": text,
            "truncated": truncated,
            "binary": "Binary files" in text[:2000] and "@@" not in text,
        }

    @classmethod
    def get_commit(cls, repository_id: str, commit_hash: str) -> dict:
        repository = cls._get_repository(repository_id)
        if not COMMIT_HASH.match(commit_hash):
            raise ValueError("잘못된 커밋 해시입니다.")
        exists = cls._run(
            repository.path, "cat-file", "-e", f"{commit_hash}^{{commit}}", timeout=10
        )
        if exists.returncode != 0:
            raise KeyError("커밋을 찾을 수 없습니다.")
        meta = cls._text(
            repository.path,
            "show",
            "-s",
            "--format=%H%x1f%an%x1f%ae%x1f%aI%x1f%cn%x1f%cI%x1f%P%x1f%B",
            commit_hash,
        ).split("\x1f", 7)
        files = []
        for line in cls._text(
            repository.path,
            "show",
            "--format=",
            "--numstat",
            "--find-renames",
            "--diff-merges=first-parent",
            commit_hash,
        ).splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                files.append(
                    {
                        "added": None if parts[0] == "-" else int(parts[0]),
                        "deleted": None if parts[1] == "-" else int(parts[1]),
                        "path": parts[-1],
                    }
                )
        patch = cls._run(
            repository.path,
            "show",
            "--format=",
            "--patch",
            "--find-renames",
            "--diff-merges=first-parent",
            commit_hash,
            timeout=30,
        ).stdout
        text, truncated = cls._limit(patch)
        return {
            "hash": meta[0] if meta else commit_hash,
            "author": meta[1] if len(meta) > 1 else "",
            "author_email": meta[2] if len(meta) > 2 else "",
            "date": meta[3] if len(meta) > 3 else "",
            "committer": meta[4] if len(meta) > 4 else "",
            "parents": meta[6].split() if len(meta) > 6 else [],
            "message": meta[7].strip() if len(meta) > 7 else "",
            "files": files,
            "diff": text,
            "truncated": truncated,
        }

    # ── 작업 실행 ───────────────────────────────────────────────────────
    @classmethod
    def _lock_for(cls, repository_id: str) -> threading.Lock:
        with cls._locks_guard:
            return cls._repository_locks.setdefault(repository_id, threading.Lock())

    @classmethod
    def _valid_paths(
        cls, path: Path, requested: list[str] | None, predicate
    ) -> list[dict[str, Any]]:
        """요청한 경로가 현재 변경 목록에 실제로 있는 파일인지 확인한다."""
        changes = [change for change in cls._changes(path) if predicate(change)]
        if requested is None:
            return changes
        by_path = {change["path"]: change for change in changes}
        selected = []
        for item in requested:
            change = by_path.get(item)
            if change is None:
                raise ValueError(f"대상이 아닌 파일입니다: {item}")
            selected.append(change)
        return selected

    @classmethod
    def _refs(cls, path: Path, namespace: str) -> set[str]:
        return set(
            cls._text(
                path, "for-each-ref", "--format=%(refname:short)", namespace
            ).splitlines()
        )

    @classmethod
    def _validate_new_branch(cls, path: Path, name: str) -> str:
        name = (name or "").strip()
        if not name or name.startswith("-") or len(name) > 200:
            raise ValueError("브랜치 이름이 올바르지 않습니다.")
        if (
            cls._run(path, "check-ref-format", "--branch", name, timeout=10).returncode
            != 0
        ):
            raise ValueError("브랜치 이름이 올바르지 않습니다.")
        if name in cls._refs(path, "refs/heads"):
            raise ValueError("이미 있는 브랜치입니다.")
        return name

    @classmethod
    def _existing_ref(cls, path: Path, name: str, allow_remote: bool = True) -> str:
        name = (name or "").strip()
        refs = cls._refs(path, "refs/heads")
        if allow_remote:
            refs |= {
                ref
                for ref in cls._refs(path, "refs/remotes")
                if not ref.endswith("/HEAD")
            }
        if not name or name.startswith("-") or name not in refs:
            raise ValueError("존재하지 않는 브랜치입니다.")
        return name

    @classmethod
    def _existing_stash(cls, path: Path, ref: str) -> str:
        if not STASH_REF.match(ref or "") or ref not in {
            stash["ref"] for stash in cls._stashes(path)
        }:
            raise ValueError("존재하지 않는 stash 입니다.")
        return ref

    @classmethod
    def _push_args(cls, path: Path, force: bool = False) -> list[str]:
        branch = cls._text(path, "branch", "--show-current")
        if not branch:
            raise ValueError("detached HEAD 상태에서는 Push할 수 없습니다.")
        upstream = cls._text(path, "rev-parse", "--abbrev-ref", "@{upstream}")
        origin = cls._text(path, "remote", "get-url", "origin")
        if not upstream and not origin:
            raise ValueError("Push할 origin 원격 저장소가 없습니다.")
        args = ["push"] if upstream else ["push", "--set-upstream", "origin", branch]
        if force:
            args.insert(1, "--force-with-lease")
        return args

    @classmethod
    def _plan(cls, path: Path, action: str, options: dict[str, Any]) -> list[list[str]]:
        """작업을 git 명령 목록으로 바꾼다. 앞 명령이 실패하면 뒤 명령은 실행하지 않는다."""
        paths = options.get("paths")
        if action == "fetch":
            return [["fetch", "--all", "--prune"]]
        if action == "pull":
            return [["pull", "--rebase" if options.get("rebase") else "--no-rebase"]]
        if action == "push":
            return [cls._push_args(path, bool(options.get("force")))]

        if action == "stage":
            selected = cls._valid_paths(path, paths, lambda change: change["unstaged"])
            if not selected:
                raise ValueError("스테이징할 변경사항이 없습니다.")
            if paths is None:
                return [["add", "-A"]]
            return [["add", "-A", "--", *[change["path"] for change in selected]]]

        if action == "unstage":
            selected = cls._valid_paths(path, paths, lambda change: change["staged"])
            if not selected:
                raise ValueError("스테이징된 변경사항이 없습니다.")
            targets = []
            for change in selected:
                targets.append(change["path"])
                if change["original_path"]:
                    targets.append(change["original_path"])
            if cls._has_head(path):
                return [["reset", "-q", "HEAD", "--", *targets]]
            return [["rm", "--cached", "-r", "-q", "--", *targets]]

        if action == "discard":
            selected = cls._valid_paths(
                path,
                paths,
                lambda change: change["unstaged"] and not change["conflict"],
            )
            if not selected:
                raise ValueError("되돌릴 변경사항이 없습니다.")
            tracked = [change["path"] for change in selected if not change["untracked"]]
            untracked = [change["path"] for change in selected if change["untracked"]]
            commands = []
            if tracked:
                commands.append(["restore", "--worktree", "--", *tracked])
            if untracked:
                commands.append(["clean", "-f", "-q", "--", *untracked])
            return commands

        if action == "commit":
            message = (options.get("message") or "").strip()
            amend = bool(options.get("amend"))
            operation = cls._operation(path)
            commands = []
            if options.get("stage_all"):
                commands.append(["add", "-A"])
            else:
                staged = [change for change in cls._changes(path) if change["staged"]]
                if not staged and not amend and operation != "merge":
                    raise ValueError(
                        "스테이징된 변경사항이 없습니다. 먼저 파일을 스테이징하세요."
                    )
                if any(change["conflict"] for change in cls._changes(path)):
                    raise ValueError("해결되지 않은 충돌 파일이 있습니다.")
            commit = ["commit"]
            if amend:
                if not cls._has_head(path):
                    raise ValueError("수정할 커밋이 없습니다.")
                commit.append("--amend")
            if message:
                commit += ["-m", message]
            elif amend or operation == "merge":
                commit.append("--no-edit")
            else:
                raise ValueError("커밋 메시지를 입력하세요.")
            commands.append(commit)
            if options.get("push_after"):
                commands.append(
                    cls._push_args(path, force=amend and bool(options.get("force")))
                )
            return commands

        if action == "checkout":
            name = cls._existing_ref(path, options.get("branch", ""))
            if name in cls._refs(path, "refs/heads"):
                return [["switch", name]]
            # 원격 브랜치: 같은 이름의 로컬 추적 브랜치를 만들어 전환한다.
            local_name = name.split("/", 1)[1] if "/" in name else name
            if local_name in cls._refs(path, "refs/heads"):
                return [["switch", local_name]]
            return [["switch", "--track", name]]

        if action == "create_branch":
            name = cls._validate_new_branch(path, options.get("branch", ""))
            start = options.get("start_point")
            command = (
                ["switch", "-c", name]
                if options.get("switch", True)
                else ["branch", name]
            )
            if start:
                command.append(cls._existing_ref(path, start))
            return [command]

        if action == "delete_branch":
            name = cls._existing_ref(
                path, options.get("branch", ""), allow_remote=False
            )
            if name == cls._text(path, "branch", "--show-current"):
                raise ValueError("현재 브랜치는 삭제할 수 없습니다.")
            return [["branch", "-D" if options.get("force") else "-d", name]]

        if action == "merge":
            name = cls._existing_ref(path, options.get("branch", ""))
            if name == cls._text(path, "branch", "--show-current"):
                raise ValueError("현재 브랜치 자신은 병합할 수 없습니다.")
            if cls._operation(path):
                raise ValueError(
                    "다른 Git 작업이 진행 중입니다. 먼저 완료하거나 중단하세요."
                )
            command = ["merge", "--no-edit"]
            if options.get("squash"):
                command.append("--squash")
            elif options.get("no_ff"):
                command.append("--no-ff")
            command.append(name)
            return [command]

        if action == "abort_operation":
            operation = cls._operation(path)
            if not operation:
                raise ValueError("진행 중인 merge/rebase 작업이 없습니다.")
            return [[operation, "--abort"]]

        if action == "stash":
            command = ["stash", "push"]
            if options.get("include_untracked"):
                command.append("--include-untracked")
            message = (options.get("message") or "").strip()
            if message:
                command += ["-m", message]
            return [command]

        if action in {"stash_apply", "stash_pop", "stash_drop"}:
            ref = cls._existing_stash(path, options.get("stash_ref", ""))
            return [["stash", action.split("_", 1)[1], ref]]

        if action == "undo_commit":
            if (
                cls._run(
                    path, "rev-parse", "--verify", "-q", "HEAD~1", timeout=10
                ).returncode
                != 0
            ):
                raise ValueError("되돌릴 이전 커밋이 없습니다.")
            upstream = cls._text(path, "rev-parse", "--abbrev-ref", "@{upstream}")
            if upstream:
                unpushed = cls._text(path, "rev-list", "--count", f"{upstream}..HEAD")
                if unpushed == "0":
                    raise ValueError(
                        "이미 푸시된 커밋입니다. 되돌리려면 Revert를 사용하세요."
                    )
            return [["reset", "--soft", "HEAD~1"]]

        if action == "revert":
            commit_hash = options.get("commit", "")
            if not COMMIT_HASH.match(commit_hash or ""):
                raise ValueError("잘못된 커밋 해시입니다.")
            if (
                cls._run(
                    path, "cat-file", "-e", f"{commit_hash}^{{commit}}", timeout=10
                ).returncode
                != 0
            ):
                raise ValueError("커밋을 찾을 수 없습니다.")
            return [["revert", "--no-edit", commit_hash]]

        raise ValueError("지원하지 않는 Git 작업입니다.")

    @classmethod
    def ruff_format(cls, repository_id: str) -> dict:
        """저장소 최상위에서 `ruff format .` (커밋 전에 코드 정리). 터미널에 뜨는 요약을 그대로 돌려준다."""
        repository = cls._get_repository(repository_id)
        root = repository.path
        local = root / ".venv" / "bin" / "ruff"
        bundled = Path(sys.executable).with_name("ruff")
        if local.exists():
            command = [str(local)]
        elif shutil.which("ruff"):
            command = [shutil.which("ruff")]
        elif bundled.exists():
            command = [str(bundled)]
        elif shutil.which("uvx"):
            command = [shutil.which("uvx"), "ruff"]
        else:
            raise RuntimeError(
                "ruff 를 찾을 수 없습니다. 저장소 .venv 에 ruff 를 설치하거나 uv 를 설치하세요."
            )
        args = [*command, "format", "."]
        lock = cls._lock_for(repository.id)
        if not lock.acquire(blocking=False):
            raise ValueError("이 저장소에서 다른 작업이 실행 중입니다.")
        try:
            env = {**os.environ, "NO_COLOR": "1"}
            try:
                result = subprocess.run(
                    args,
                    cwd=root,
                    capture_output=True,
                    text=True,
                    timeout=cls.COMMAND_TIMEOUT_SECONDS,
                    env=env,
                    stdin=subprocess.DEVNULL,
                )
            except subprocess.TimeoutExpired:
                return {
                    "success": False,
                    "command": "ruff format .",
                    "output": "시간 안에 끝나지 않았습니다.",
                    "return_code": -1,
                    "summary": "",
                }
        finally:
            lock.release()
        output = "\n".join(
            part for part in (result.stdout.strip(), result.stderr.strip()) if part
        )
        summary = next(
            (
                line.strip()
                for line in reversed(output.splitlines())
                if re.search(
                    r"\bfiles? (reformatted|left unchanged)|\bfile(s)? would be", line
                )
            ),
            "",
        )
        where = (
            "~" + str(root)[len(str(Path.home())) :]
            if str(root).startswith(str(Path.home()))
            else str(root)
        )
        return {
            "success": result.returncode == 0,
            "command": f"cd {where} && ruff format .",
            "output": output or "(출력 없음)",
            "return_code": result.returncode,
            "summary": summary,
        }

    @classmethod
    def run_action(
        cls,
        repository_id: str,
        action: str,
        options: dict[str, Any] | bool | None = None,
    ) -> dict:
        if isinstance(options, bool):
            options = {"rebase": options}
        options = options or {}
        repository = cls._get_repository(repository_id)
        if action not in cls.ACTIONS:
            raise ValueError("지원하지 않는 Git 작업입니다.")

        lock = cls._lock_for(repository.id)
        if not lock.acquire(blocking=False):
            raise ValueError("이 저장소에서 다른 Git 작업이 실행 중입니다.")
        try:
            commands = cls._plan(repository.path, action, options)
            started_at = datetime.now(UTC).isoformat()
            outputs = []
            return_code = 0
            executed = []
            for args in commands:
                executed.append("git " + " ".join(args))
                try:
                    result = cls._run(repository.path, *args)
                except subprocess.TimeoutExpired:
                    outputs.append(
                        f"{cls.COMMAND_TIMEOUT_SECONDS}초 안에 작업이 끝나지 않아 중단했습니다."
                    )
                    return_code = -1
                    break
                output = "\n".join(
                    part
                    for part in (result.stdout.strip(), result.stderr.strip())
                    if part
                )
                if output:
                    outputs.append(output)
                return_code = result.returncode
                if result.returncode != 0:
                    break
            success = return_code == 0
            return {
                "success": success,
                "action": action,
                "command": " && ".join(executed),
                "output": cls._mask("\n".join(outputs))
                or ("완료되었습니다." if success else "명령이 실패했습니다."),
                "return_code": return_code,
                "started_at": started_at,
            }
        finally:
            lock.release()
