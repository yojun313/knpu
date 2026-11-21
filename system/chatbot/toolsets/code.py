"""연구실 소프트웨어(저장소 코드 · 설명서) 도구 — 구성원용."""

import re
import subprocess

from .. import code_kb, manual_kb
from ..config import REPO_ROOT
from ..registry import tool

M = ("member",)


@tool(
    "list_services",
    "연구실 소프트웨어 지도: 하는 일·입력→출력·쓰임새·코드 폴더·설명서·주소. 무엇부터 볼지 모르거나, 원하는 결과를 얻는 절차(여러 프로그램 연결)를 물을 때 먼저 부른다",
    modes=M,
    label="서비스 목록 확인",
    cache_s=300,
    reads=True,
)
def list_services(ctx):
    from .. import tools

    return tools.list_services()


@tool(
    "search_manual",
    "서비스 설명서(사용법 문서) 검색. 사용법·절차·옵션 뜻·제한 사항 질문은 코드보다 이것을 먼저 쓴다. 구역 id 와 본문 앞부분을 돌려줌",
    {
        "query": "검색어(기능 이름·화면 문구)",
        "service": "(선택) 서비스로 좁히기 예: kemkim, network, statistics, mcdm, manager",
    },
    modes=M,
    label="설명서 검색 · {query}",
    cache_s=120,
    reads=True,
)
def search_manual(ctx, query="", service=""):
    hits = manual_kb.search(str(query), str(service))
    if not hits:
        return {
            "count": 0,
            "note": "설명서에 없습니다. 다른 낱말로 찾거나 search_code 로 화면 코드를 확인해 주시기 바랍니다.",
        }
    return {"count": len(hits), "results": hits}


@tool(
    "read_manual",
    "설명서 구역 전문 읽기(하위 구역 포함, HTML 태그 없는 본문). id 는 search_manual·manual_toc 결과의 id",
    {"id": "구역 id 또는 구역 제목"},
    modes=M,
    label="설명서 읽기 · {id}",
    cache_s=120,
    reads=True,
)
def read_manual(ctx, id=""):
    doc = manual_kb.read(str(id))
    if not doc:
        raise ValueError(
            "없는 구역입니다. search_manual 또는 manual_toc 결과의 id 를 그대로 써 주시기 바랍니다."
        )
    return doc


@tool(
    "manual_toc",
    "설명서 목차(구역 제목과 id). 설명서에 무엇이 있는지 훑을 때",
    {"service": "(선택) 서비스 예: kemkim"},
    modes=M,
    label="설명서 목차 · {service}",
    cache_s=120,
)
def manual_toc(ctx, service=""):
    return manual_kb.toc(str(service))


@tool(
    "search_code",
    "저장소 코드·설명서 키워드 검색(경로·줄 번호와 발췌를 돌려줌)",
    {
        "query": "검색어(기능 이름·화면 문구·함수명)",
        "path": "(선택) 폴더로 좁히기 예: kemkim/",
    },
    modes=M,
    label="코드 검색 · {query}",
    cache_s=120,
    reads=True,
)
def search_code(ctx, query="", path=""):
    hits = code_kb.index.search(str(query), str(path))
    if not hits:
        return {
            "count": 0,
            "note": "결과 없음. 화면에 보이는 문구나 영어 함수명으로 바꿔 찾거나 grep 을 써 보시기 바랍니다.",
        }
    return {"count": len(hits), "results": hits}


@tool(
    "grep",
    "정확한 문자열/정규식 검색(함수·라우트·설정 키 찾기). 전체 일치 파일 수를 함께 돌려줌",
    {"pattern": "문자열 또는 정규식", "path": "(선택) 폴더"},
    modes=M,
    label="정확히 찾기 · {pattern}",
    cache_s=120,
    reads=True,
)
def grep(ctx, pattern="", path=""):
    return code_kb.grep(str(pattern), str(path))


@tool(
    "read_file",
    "파일 일부 읽기(최대 220줄, 줄 번호 포함)",
    {
        "path": "저장소 기준 경로",
        "start": "(선택) 시작 줄(기본 1)",
        "end": "(선택) 끝 줄",
    },
    modes=M,
    label="파일 읽기 · {path}",
    cache_s=60,
    reads=True,
)
def read_file(ctx, path="", start="", end=""):
    try:
        s = int(start or 1)
        e = int(end) if str(end).strip() else None
    except (TypeError, ValueError):
        raise ValueError(
            "start·end 는 줄 번호(정수)로 입력해 주시기 바랍니다."
        ) from None
    return code_kb.read_file(str(path), s, e)


@tool(
    "list_dir",
    "폴더 안의 하위 폴더·파일 목록",
    {"path": "(선택) 저장소 기준 폴더(비우면 루트)"},
    modes=M,
    label="폴더 보기 · {path}",
    cache_s=120,
)
def list_dir(ctx, path=""):
    return code_kb.list_dir(str(path))


@tool(
    "find_files",
    "파일 이름으로 찾기(경로 일부·확장자). 예: 'viewer.js', 'kemkim routes'",
    {"name": "파일 이름 또는 경로 일부(띄어쓰기로 여러 조건)", "path": "(선택) 폴더"},
    modes=M,
    label="파일 찾기 · {name}",
    cache_s=120,
)
def find_files(ctx, name="", path=""):
    words = [w.lower() for w in str(name).split() if w]
    if not words:
        raise ValueError("찾을 파일 이름을 입력해 주시기 바랍니다.")
    prefix = str(path).strip().lstrip("/")
    hits = [
        f
        for f in code_kb.tracked_files()
        if (not prefix or f.startswith(prefix)) and all(w in f.lower() for w in words)
    ]
    hits.sort(key=lambda f: (len(f.split("/")), len(f)))
    return {
        "count": len(hits),
        "results": [{"path": f} for f in hits[:40]],
        "truncated": len(hits) > 40,
    }


_OUTLINE = {
    ".py": re.compile(r"^(\s*)(?:async\s+)?(def|class)\s+([A-Za-z_]\w*)"),
    ".js": re.compile(
        r"^(\s*)(?:export\s+)?(?:async\s+)?(function|class)\s+([A-Za-z_$][\w$]*)"
    ),
    ".html": re.compile(
        r"^(\s*)<(h[1-4]|section|form|dialog)\b[^>]*?(?:id=\"([^\"]+)\")"
    ),
    ".md": re.compile(r"^()(#{1,4})\s+(.+)$"),
}
_ROUTE = re.compile(r"^\s*@\w+\.(get|post|put|patch|delete)\(\s*f?[\"']([^\"']+)")


@tool(
    "file_outline",
    "파일의 뼈대(함수·클래스·라우트·제목과 줄 번호). 큰 파일에서 읽을 위치를 정할 때 read_file 전에 쓴다",
    {"path": "저장소 기준 경로"},
    modes=M,
    label="파일 구조 · {path}",
    cache_s=120,
)
def file_outline(ctx, path=""):
    p = code_kb.safe_path(str(path))
    if not p.is_file():
        raise ValueError(f"파일이 없습니다: {path}")
    if p.stat().st_size > 2_000_000:
        raise ValueError("파일이 너무 커서 읽을 수 없습니다.")
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    rx = (
        _OUTLINE.get(p.suffix.lower())
        or _OUTLINE[".py" if p.suffix == ".pyi" else ".js"]
    )
    items = []
    for i, line in enumerate(lines, 1):
        r = _ROUTE.match(line)
        if r:
            items.append(
                {
                    "line": i,
                    "kind": "route",
                    "name": f"{r.group(1).upper()} {r.group(2)}",
                }
            )
            continue
        m = rx.match(line)
        if m and (m.group(3) or "").strip():
            items.append(
                {
                    "line": i,
                    "kind": m.group(2),
                    "name": m.group(3).strip()[:80],
                    "depth": len(m.group(1)) // 2,
                }
            )
    rel = str(p.relative_to(REPO_ROOT.resolve()))
    return {
        "path": rel,
        "total_lines": len(lines),
        "count": len(items),
        "items": items[:200],
        "truncated": len(items) > 200,
    }


@tool(
    "recent_changes",
    "최근 코드 변경 이력(git 커밋 제목·날짜·바뀐 파일 수). '최근에 뭐가 바뀌었나', '이 기능 언제 고쳤나' 질문에 쓴다",
    {
        "path": "(선택) 폴더·파일로 좁히기 예: crawler/",
        "limit": "(선택) 개수(기본 15, 최대 40)",
    },
    modes=M,
    label="최근 변경 · {path}",
    cache_s=120,
)
def recent_changes(ctx, path="", limit=""):
    try:
        n = max(1, min(40, int(limit or 15)))
    except (TypeError, ValueError):
        n = 15
    cmd = [
        "git",
        "-C",
        str(REPO_ROOT),
        "log",
        f"-n{n}",
        "--date=short",
        "--pretty=format:%h\t%ad\t%s",
        "--shortstat",
    ]
    rel = str(path).strip().lstrip("/")
    if rel:
        code_kb.safe_path(rel)  # 저장소 밖 경로 차단
        cmd += ["--", rel]
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=15).stdout.decode(
            "utf-8", "replace"
        )
    except Exception as e:
        raise ValueError(f"변경 이력을 읽지 못했습니다: {type(e).__name__}") from e
    commits = []
    for line in out.splitlines():
        if "\t" in line:
            h, d, s = (line.split("\t", 2) + ["", ""])[:3]
            commits.append({"commit": h, "date": d, "subject": code_kb.redact(s)[:200]})
        elif line.strip() and commits:
            m = re.search(r"(\d+) files? changed", line)
            if m:
                commits[-1]["files_changed"] = int(m.group(1))
    return {"count": len(commits), "path": rel or "(전체)", "commits": commits}
