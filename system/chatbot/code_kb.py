"""knpu 저장소 코드 색인 — 구성원용 챗봇이 코드를 직접 찾고 읽는 도구의 바탕.

- 대상: `git ls-files` 로 추적되는 텍스트 파일만 (.gitignore 된 .env · 데이터 · 가상환경은 원천 제외).
  비밀이 들어 있을 법한 이름(.env, *secret*, *credential*, *.pem 등)은 한 번 더 뺀다.
- 색인: SQLite FTS5 trigram (dis-047 과 같은 방식). 파일을 60줄 안팎의 조각으로 나눠 경로 · 줄 범위와 함께
  넣는다. 트라이그램은 두 글자 한국어 단어("작업", "설정")를 못 찾으므로 그런 단어는 LIKE 로 보조한다.
- 모든 사이트 프로세스가 같은 색인 파일(~/.knpu_chatbot/code.sqlite)을 쓴다. 5분마다 파일 수정 시각을
  훑어 바뀐 파일만 다시 넣는다.
- 읽기 결과는 비밀처럼 보이는 값(API 키 · 비밀번호 · 토큰 · 접속 문자열)을 가려서 돌려준다.
"""

import fnmatch
import logging
import os
import re
import sqlite3
import subprocess
import threading
import time
from pathlib import Path

from .config import CODE_RESCAN_S, REPO_ROOT, data_dir

logger = logging.getLogger(__name__)

TEXT_EXT = {
    ".py",
    ".js",
    ".mjs",
    ".ts",
    ".html",
    ".css",
    ".md",
    ".json",
    ".toml",
    ".yml",
    ".yaml",
    ".txt",
    ".sh",
    ".sql",
    ".cfg",
    ".ini",
    ".jinja",
    ".j2",
    ".example",
}
DENY_NAMES = [
    "*.env",
    ".env*",
    "*secret*",
    "*credential*",
    "*.pem",
    "*.key",
    "id_rsa*",
    "*.p12",
    "*token*.json",
]
DENY_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
    "storage",
    "logs",
    "dist",
    "build",
}
MAX_FILE_BYTES = 400_000
CHUNK_LINES = 60
CHUNK_OVERLAP = 8

_SECRET_PATTERNS = [
    re.compile(
        r"(?i)((?:api[_-]?key|secret|passw(?:or)?d|token|private[_-]?key|access[_-]?key)\s*[:=]\s*)(['\"])([^'\"\n]{6,})(\2)"
    ),
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)(mongodb(?:\+srv)?://[^:\s/]+:)([^@\s]+)(@)"),
    re.compile(r"\b(?:ghp|gho|github_pat)_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
]


def redact(text: str) -> str:
    text = _SECRET_PATTERNS[0].sub(
        lambda m: f"{m.group(1)}{m.group(2)}***{m.group(4)}", text
    )
    text = _SECRET_PATTERNS[1].sub("sk-***", text)
    text = _SECRET_PATTERNS[2].sub(lambda m: f"{m.group(1)}***{m.group(3)}", text)
    text = _SECRET_PATTERNS[3].sub("***", text)
    text = _SECRET_PATTERNS[4].sub("***", text)
    return text


def _allowed(rel: str) -> bool:
    parts = rel.split("/")
    if any(p in DENY_DIRS for p in parts[:-1]):
        return False
    name = parts[-1]
    if any(
        fnmatch.fnmatch(name.lower(), pat) for pat in DENY_NAMES
    ) and not name.endswith(".example"):
        return False
    return Path(name).suffix.lower() in TEXT_EXT or name in {"Dockerfile", "Makefile"}


def tracked_files() -> list[str]:
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files", "-z"],
            capture_output=True,
            timeout=20,
        )
        files = [f for f in out.stdout.decode("utf-8", "replace").split("\0") if f]
    except Exception:
        files = []
    if not files:  # git 이 없으면 폴더를 훑는다
        for root, dirs, names in os.walk(REPO_ROOT):
            dirs[:] = [d for d in dirs if d not in DENY_DIRS and not d.startswith(".")]
            for n in names:
                files.append(os.path.relpath(os.path.join(root, n), REPO_ROOT))
    return sorted(f for f in files if _allowed(f))


def safe_path(rel: str) -> Path:
    """저장소 밖 · 제외 대상 경로는 거절한다."""
    rel = (rel or "").strip().lstrip("/")
    path = (REPO_ROOT / rel).resolve()
    if path != REPO_ROOT.resolve() and REPO_ROOT.resolve() not in path.parents:
        raise ValueError("저장소 밖의 경로는 읽을 수 없습니다.")
    rel_norm = (
        str(path.relative_to(REPO_ROOT.resolve()))
        if path != REPO_ROOT.resolve()
        else ""
    )
    if rel_norm and path.is_file() and not _allowed(rel_norm):
        raise ValueError(
            "이 파일은 보안상 챗봇이 읽을 수 없습니다(비밀 설정 · 데이터 파일)."
        )
    return path


# ── 색인 ────────────────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, mtime REAL, size INTEGER);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(path, start UNINDEXED, stop UNINDEXED, body, tokenize='trigram');
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
"""


class CodeIndex:
    def __init__(self):
        self.path = data_dir() / "code.sqlite"
        self.lock = threading.Lock()
        self.last_scan = 0.0

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=30)
        con.execute("PRAGMA journal_mode=WAL")
        con.executescript(_SCHEMA)
        return con

    def refresh(self, force: bool = False) -> dict:
        """바뀐 파일만 다시 색인한다(여러 프로세스가 동시에 불러도 안전하게 SQLite 트랜잭션으로)."""
        with self.lock:
            if not force and time.time() - self.last_scan < CODE_RESCAN_S:
                return {}
            con = self._connect()
            try:
                known = {
                    p: (m, s)
                    for p, m, s in con.execute("SELECT path, mtime, size FROM files")
                }
                files = tracked_files()
                current = set()
                changed = 0
                con.execute("BEGIN IMMEDIATE")
                for rel in files:
                    full = REPO_ROOT / rel
                    try:
                        st = full.stat()
                    except OSError:
                        continue
                    if st.st_size > MAX_FILE_BYTES:
                        continue
                    current.add(rel)
                    if known.get(rel) == (st.st_mtime, st.st_size):
                        continue
                    try:
                        text = full.read_text(encoding="utf-8")
                    except (UnicodeDecodeError, OSError):
                        continue
                    con.execute("DELETE FROM chunks WHERE path = ?", (rel,))
                    lines = text.splitlines()
                    step = CHUNK_LINES - CHUNK_OVERLAP
                    for start in range(0, max(len(lines), 1), step):
                        body = "\n".join(lines[start : start + CHUNK_LINES])
                        if body.strip():
                            con.execute(
                                "INSERT INTO chunks(path, start, stop, body) VALUES (?,?,?,?)",
                                (
                                    rel,
                                    start + 1,
                                    min(start + CHUNK_LINES, len(lines)),
                                    body,
                                ),
                            )
                        if start + CHUNK_LINES >= len(lines):
                            break
                    con.execute(
                        "INSERT OR REPLACE INTO files VALUES (?,?,?)",
                        (rel, st.st_mtime, st.st_size),
                    )
                    changed += 1
                removed = [p for p in known if p not in current]
                for p in removed:
                    con.execute("DELETE FROM chunks WHERE path = ?", (p,))
                    con.execute("DELETE FROM files WHERE path = ?", (p,))
                con.execute("COMMIT")
                self.last_scan = time.time()
                if changed or removed:
                    logger.info(
                        "코드 색인 갱신: %d개 변경, %d개 삭제", changed, len(removed)
                    )
                return {
                    "files": len(current),
                    "changed": changed,
                    "removed": len(removed),
                }
            except Exception:
                try:
                    con.execute("ROLLBACK")
                except Exception:
                    pass
                raise
            finally:
                con.close()

    def search(self, query: str, path_prefix: str = "", limit: int = 10) -> list[dict]:
        self.refresh()
        terms = [t for t in re.findall(r"[\w가-힣.\-/]+", query or "") if t]
        long_terms = [t for t in terms if len(t) >= 3]
        short_terms = [t for t in terms if len(t) < 3]
        if not terms:
            return []
        con = self._connect()
        try:
            rows = []
            prefix = (path_prefix or "").strip().lstrip("/")
            if long_terms:
                match = " OR ".join('"' + t.replace('"', "") + '"' for t in long_terms)
                sql = "SELECT path, start, stop, body, bm25(chunks, 4.0, 0, 0, 1.0) AS r FROM chunks WHERE chunks MATCH ?"
                params: list = [match]
                if prefix:
                    sql += " AND path LIKE ?"
                    params.append(prefix + "%")
                rows = con.execute(sql + " ORDER BY r LIMIT 200", params).fetchall()
            if short_terms and len(rows) < 40:
                like = " OR ".join("body LIKE ?" for _ in short_terms)
                sql = f"SELECT path, start, stop, body, 0 FROM chunks WHERE ({like})"
                params = [f"%{t}%" for t in short_terms]
                if prefix:
                    sql += " AND path LIKE ?"
                    params.append(prefix + "%")
                rows += con.execute(sql + " LIMIT 200", params).fetchall()
        finally:
            con.close()
        # 재순위: 질문 단어가 몇 개나 들어 있는지(파일 경로 일치는 가중) + FTS 점수
        seen, scored = set(), []
        lower_terms = [t.lower() for t in terms]
        for path, start, stop, body, r in rows:
            key = (path, start)
            if key in seen:
                continue
            seen.add(key)
            low = body.lower()
            hits = sum(1 for t in lower_terms if t in low)
            path_hits = sum(1 for t in lower_terms if t in path.lower())
            score = hits * 2 + path_hits * 3 - float(r or 0) * 0.2
            if path.endswith((".md", "manual.html")) or "/manuals/" in path:
                score += 1.5  # 설명서 · 문서는 사용법 질문에 먼저
            scored.append((score, path, start, stop, body))
        scored.sort(key=lambda x: -x[0])
        out = []
        for score, path, start, stop, body in scored[:limit]:
            lines = body.splitlines()
            best = (
                max(
                    range(len(lines)),
                    key=lambda i: sum(t in lines[i].lower() for t in lower_terms),
                )
                if lines
                else 0
            )
            snippet = "\n".join(lines[max(0, best - 2) : best + 4])
            out.append(
                {
                    "path": path,
                    "lines": f"{start + max(0, best - 2)}-{min(stop, start + best + 3)}",
                    "chunk": f"{start}-{stop}",
                    "snippet": redact(snippet)[:500],
                    "score": round(score, 1),
                }
            )
        return out

    def stats(self) -> dict:
        self.refresh()
        con = self._connect()
        try:
            return {
                "files": con.execute("SELECT count(*) FROM files").fetchone()[0],
                "chunks": con.execute("SELECT count(*) FROM chunks").fetchone()[0],
            }
        finally:
            con.close()


index = CodeIndex()


def read_file(
    rel: str, start: int = 1, end: int | None = None, max_lines: int = 220
) -> dict:
    path = safe_path(rel)
    if not path.is_file():
        raise ValueError(f"파일이 없습니다: {rel}")
    if path.stat().st_size > 2_000_000:
        raise ValueError("파일이 너무 커서 읽을 수 없습니다.")
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    total = len(lines)
    start = max(1, int(start or 1))
    end = min(total, int(end) if end else start + max_lines - 1, start + max_lines - 1)
    body = "\n".join(f"{i:>5}  {lines[i - 1]}" for i in range(start, end + 1))
    out = {
        "path": str(path.relative_to(REPO_ROOT.resolve())),
        "lines": f"{start}-{end}",
        "total_lines": total,
        "truncated": end < total,
        "text": redact(body),
    }
    if start == 1 and total > 300:
        # 큰 화면 파일은 앞부분이 스타일(CSS)뿐인 경우가 많다 — 필요한 줄을 먼저 찾게 안내한다
        out["note"] = (
            f"전체 {total}줄 중 앞 {end}줄만 보냈습니다. 필요한 부분은 search_code/grep 결과의 줄 번호로 "
            "start 를 지정해 읽으세요."
        )
    return out


def list_dir(rel: str = "") -> dict:
    path = safe_path(rel)
    if not path.is_dir():
        raise ValueError(f"폴더가 아닙니다: {rel}")
    tracked = tracked_files()
    base = (
        str(path.relative_to(REPO_ROOT.resolve()))
        if path != REPO_ROOT.resolve()
        else ""
    )
    prefix = base + "/" if base else ""
    dirs: dict = {}
    files = []
    for f in tracked:
        if not f.startswith(prefix):
            continue
        rest = f[len(prefix) :]
        if "/" in rest:
            d = rest.split("/", 1)[0]
            dirs[d] = dirs.get(d, 0) + 1
        else:
            files.append(rest)
    return {
        "path": base or ".",
        "dirs": [{"name": d + "/", "files": n} for d, n in sorted(dirs.items())],
        "files": files[:150],
        "truncated": len(files) > 150,
    }


def grep(pattern: str, path_prefix: str = "", limit: int = 40) -> dict:
    """정확한 문자열 · 정규식 검색 (함수 이름 · 설정 키 · 라우트 경로 찾기)."""
    try:
        rx = re.compile(pattern, re.I)
    except re.error:
        rx = re.compile(re.escape(pattern), re.I)
    prefix = (path_prefix or "").strip().lstrip("/")
    hits, files_hit = [], set()
    for rel in tracked_files():
        if prefix and not rel.startswith(prefix):
            continue
        full = REPO_ROOT / rel
        try:
            if full.stat().st_size > MAX_FILE_BYTES:
                continue
            for i, line in enumerate(full.read_text(encoding="utf-8").splitlines(), 1):
                if rx.search(line):
                    files_hit.add(rel)
                    if len(hits) < limit:
                        hits.append(
                            {"path": rel, "line": i, "text": redact(line.strip())[:220]}
                        )
        except (UnicodeDecodeError, OSError):
            continue
    # 건수는 잘리지 않은 전체 기준으로 코드가 센다
    return {
        "match_files": len(files_hit),
        "shown": len(hits),
        "hits": hits,
        "truncated": len(hits) >= limit,
    }
