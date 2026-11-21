"""서비스 설명서(manual*.html) 색인 — 설명서를 제목 단위 구역으로 나눠 바로 찾고 읽는다.

코드 검색 → 파일 읽기(HTML 태그 포함 220줄)보다, 설명서의 해당 구역 본문만 깨끗한 글로 주는 편이
사용법 질문에 훨씬 빠르고 정확하다. 설명서 파일은 저장소에 추적되는 것만 대상으로 하고,
파일이 바뀌면(수정 시각) 다시 읽는다.
"""

import re
import threading
import time
from html.parser import HTMLParser

from . import code_kb
from .config import REPO_ROOT
from .search import BM25

_SKIP = {"script", "style", "nav", "svg", "noscript", "template", "head"}
_HEAD = {"h1", "h2", "h3", "h4"}
_BLOCK = {
    "p",
    "li",
    "tr",
    "div",
    "section",
    "br",
    "table",
    "ul",
    "ol",
    "pre",
    "dt",
    "dd",
}
_MAX_SECTION = 7000
_RESCAN_S = 60


class _Sections(HTMLParser):
    """제목(h1~h4)을 경계로 본문을 구역으로 나눈다."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[dict] = []
        self.skip = 0
        self.head: dict | None = None  # 지금 읽는 제목 태그
        self.cur = {"title": "", "level": 1, "anchor": "", "parts": [], "line": 1}

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self.skip += 1
        elif self.skip:
            return
        elif tag in _HEAD:
            self._flush()
            self.head = {
                "level": int(tag[1]),
                "anchor": dict(attrs).get("id") or "",
                "parts": [],
            }
            self.cur = {
                "title": "",
                "level": self.head["level"],
                "anchor": self.head["anchor"],
                "parts": [],
                "line": self.getpos()[0],
            }
        elif tag in _BLOCK:
            self.cur["parts"].append("\n")
        elif tag in ("td", "th"):
            self.cur["parts"].append(" | ")

    def handle_endtag(self, tag):
        if tag in _SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in _HEAD and self.head is not None:
            self.cur["title"] = re.sub(r"\s+", " ", "".join(self.head["parts"])).strip()
            self.head = None

    def handle_data(self, data):
        if self.skip:
            return
        (self.head["parts"] if self.head is not None else self.cur["parts"]).append(
            data
        )

    def _flush(self):
        text = "".join(self.cur["parts"])
        text = re.sub(r"[ \t\r\f\v]+", " ", text)
        text = re.sub(r"\n\s*", "\n", text).strip()
        if self.cur["title"] or len(text) > 40:
            self.out.append(
                {
                    **{k: self.cur[k] for k in ("title", "level", "anchor", "line")},
                    "text": text,
                }
            )

    def close(self):
        super().close()
        self._flush()


def _service_of(path: str) -> tuple[str, str]:
    from . import tools

    best = ("", "")
    for s in tools.SERVICES:
        code = s["code"].rstrip("/") + "/"
        root = code.split("/")[0] + "/"
        for prefix in (code, root):
            if path.startswith(prefix) and len(prefix) > len(best[1]):
                best = (s["key"], prefix)
    key = best[0]
    name = next((s["name"] for s in tools.SERVICES if s["key"] == key), "")
    # manager 의 개별 설명서(manual_whisper.html 등)는 파일 이름으로 구분한다
    m = re.search(r"manual_([a-z_]+)\.html$", path)
    if m:
        name = f"{name} · {m.group(1).replace('_', ' ')}"
    return key, name


def _manual_files() -> list[str]:
    return [
        f
        for f in code_kb.tracked_files()
        if re.search(r"(^|/)(manual[\w-]*\.html|manuals/[^/]+\.(html|md))$", f)
    ]


class _Index:
    def __init__(self):
        self.lock = threading.Lock()
        self.checked = 0.0
        self.stamp: tuple = ()
        self.sections: list[dict] = []
        self.bm25 = BM25([])

    def get(self) -> tuple[list[dict], BM25]:
        with self.lock:
            if self.sections and time.monotonic() - self.checked < _RESCAN_S:
                return self.sections, self.bm25
            files = _manual_files()
            stamp = []
            for f in files:
                try:
                    st = (REPO_ROOT / f).stat()
                    stamp.append((f, st.st_mtime, st.st_size))
                except OSError:
                    continue
            stamp = tuple(stamp)
            if stamp != self.stamp:
                self.sections = self._build([s[0] for s in stamp])
                self.bm25 = BM25(self.sections)
                self.stamp = stamp
            self.checked = time.monotonic()
            return self.sections, self.bm25

    @staticmethod
    def _build(files: list[str]) -> list[dict]:
        out = []
        for path in files:
            try:
                raw = (REPO_ROOT / path).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            key, name = _service_of(path)
            if path.endswith(".md"):
                parts = re.split(r"(?m)^(#{1,4})\s+(.+)$", raw)
                secs = (
                    [
                        {
                            "title": "",
                            "level": 1,
                            "anchor": "",
                            "line": 1,
                            "text": parts[0].strip(),
                        }
                    ]
                    if parts[0].strip()
                    else []
                )
                for i in range(1, len(parts) - 2, 3):
                    secs.append(
                        {
                            "title": parts[i + 1].strip(),
                            "level": len(parts[i]),
                            "anchor": "",
                            "line": 0,
                            "text": parts[i + 2].strip(),
                        }
                    )
            else:
                p = _Sections()
                try:
                    p.feed(raw)
                    p.close()
                except Exception:
                    continue
                secs = p.out
            trail: dict[int, str] = {}
            for n, s in enumerate(secs):
                trail = {lv: t for lv, t in trail.items() if lv < s["level"]}
                crumbs = [trail[lv] for lv in sorted(trail)]
                trail[s["level"]] = s["title"]
                out.append(
                    {
                        "id": f"{path}#{s['anchor'] or n}",
                        "service": key,
                        "service_name": name,
                        "path": path,
                        "title": s["title"] or "(머리말)",
                        "crumbs": " > ".join(c for c in crumbs if c),
                        "level": s["level"],
                        "line": s["line"],
                        "text": code_kb.redact(s["text"]),
                    }
                )
        return out


_index = _Index()


def _match_service(sec: dict, service: str) -> bool:
    s = (service or "").strip().lower()
    return (
        not s
        or s in (sec["service"], sec["service_name"].lower())
        or s in sec["path"].lower()
        or s in sec["service_name"].lower()
    )


def toc(service: str = "") -> dict:
    secs, _ = _index.get()
    items = [s for s in secs if _match_service(s, service)]
    if not items:
        return {
            "count": 0,
            "note": "해당 서비스의 설명서가 없습니다.",
            "manuals": sorted({s["service"] for s in secs}),
        }
    return {
        "count": len(items),
        "sections": [
            {
                "id": s["id"],
                "service": s["service_name"],
                "title": ("  " * (s["level"] - 1)) + s["title"],
                "chars": len(s["text"]),
            }
            for s in items
            if s["level"] <= 3
        ][:150],
    }


def search(query: str, service: str = "", limit: int = 6) -> list[dict]:
    secs, bm25 = _index.get()
    hits = bm25.search(query, limit=limit, where=lambda d: _match_service(d, service))
    return [
        {
            "id": d["id"],
            "service": d["service_name"],
            "title": (d["crumbs"] + " > " if d["crumbs"] else "") + d["title"],
            "path": d["path"],
            "snippet": d["text"][:700],
            "chars": len(d["text"]),
            "score": round(s, 2),
        }
        for s, d in hits
    ]


def read(section_id: str) -> dict | None:
    """구역 하나의 본문. 하위 구역(더 깊은 제목)도 길이 한도 안에서 이어 붙인다."""
    secs, _ = _index.get()
    sid = (section_id or "").strip()
    idx = next((i for i, s in enumerate(secs) if s["id"] == sid), None)
    if idx is None:  # 제목으로도 찾는다
        low = sid.lower()
        idx = next(
            (
                i
                for i, s in enumerate(secs)
                if low and low in f"{s['service_name']} {s['title']}".lower()
            ),
            None,
        )
    if idx is None:
        return None
    first = secs[idx]
    parts, total, included = [], 0, 0
    for s in secs[idx:]:
        if s is not first and (
            s["path"] != first["path"] or s["level"] <= first["level"]
        ):
            break
        block = (f"\n## {s['title']}\n" if s is not first else "") + s["text"]
        if total + len(block) > _MAX_SECTION and parts:
            break
        parts.append(block)
        total += len(block)
        included += 1
    text = "\n".join(parts)
    return {
        "id": first["id"],
        "service": first["service_name"],
        "title": (first["crumbs"] + " > " if first["crumbs"] else "") + first["title"],
        "path": first["path"],
        "lines": f"{first['line']}-",
        "text": text[: _MAX_SECTION + 500],
        "truncated": len(text) > _MAX_SECTION + 500,
        "subsections_included": included - 1,
    }
