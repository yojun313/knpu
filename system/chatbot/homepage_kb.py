"""연구실 홈페이지 지식 — 홈페이지에 보이는 모든 정보를 문서 단위로 모은다.

- 정적 페이지(homepage/server/app/public/*.html): 스크립트 · 내비게이션을 빼고 제목(h1~h4) 단위로 나눈다.
- 동적 콘텐츠(구성원 · 소식 · 논문 · 입학 FAQ · 갤러리 · 팝업 공지): DB에서 읽고, DB에 붙을 수 없으면
  홈페이지 공개 API(/api/members/ 등)로 읽는다. 홈페이지가 공개하는 것과 같은 범위만 쓴다.
10분 동안 캐시하고, 검색은 BM25(search.py)로 한다.
"""

import html
import logging
import re
import threading
import time
from html.parser import HTMLParser

import httpx

from .config import HOMEPAGE_CACHE_S, REPO_ROOT, homepage_api_base
from .search import BM25

logger = logging.getLogger(__name__)

PUBLIC_DIR = REPO_ROOT / "homepage" / "server" / "app" / "public"
# 외부인에게 의미 있는 공개 페이지만 (로그인 · 계정 · 관리자 화면은 제외)
PAGES = {
    "homepage.html": ("/", "홈"),
    "about.html": ("/about", "연구원 소개"),
    "people.html": ("/people", "구성원"),
    "publications.html": ("/publications", "논문"),
    "news.html": ("/news", "소식"),
    "gallery.html": ("/gallery", "갤러리"),
    "admission.html": ("/admission", "입학 안내"),
    "systems.html": ("/systems", "연구 시스템"),
    "terms.html": ("/terms", "이용약관"),
}
_SKIP_TAGS = {"script", "style", "nav", "noscript", "svg", "template", "button"}


class _Extractor(HTMLParser):
    def __init__(self, keep_footer: bool):
        super().__init__(convert_charrefs=True)
        self.keep_footer = keep_footer
        self.skip = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS or (tag == "footer" and not self.keep_footer):
            self.skip += 1
        elif tag in ("h1", "h2", "h3", "h4"):
            self.parts.append("\n␞")  # 제목 경계 표시
        elif tag in ("p", "li", "div", "br", "tr", "section", "td", "dd", "dt"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS or (tag == "footer" and not self.keep_footer):
            self.skip = max(0, self.skip - 1)
        elif tag in ("h1", "h2", "h3", "h4"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def _clean(text: str) -> str:
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln and ln not in {"‹", "›", "✕", "Launch"})


def _page_docs() -> list[dict]:
    docs = []
    for name, (path, label) in PAGES.items():
        file = PUBLIC_DIR / name
        if not file.exists():
            continue
        ex = _Extractor(keep_footer=(name == "homepage.html"))
        ex.feed(file.read_text(encoding="utf-8", errors="replace"))
        text = "".join(ex.parts)
        chunks = [c for c in text.split("␞")]
        # 제목 하나에 본문이 너무 짧으면 다음 조각과 합친다
        merged, buf = [], ""
        for c in chunks:
            buf = (buf + "\n" + c) if buf else c
            if len(_clean(buf)) >= 160:
                merged.append(buf)
                buf = ""
        if buf:
            merged.append(buf)
        for i, chunk in enumerate(merged):
            body = _clean(chunk)
            if len(body) < 20:
                continue
            first = body.split("\n", 1)[0][:60]
            docs.append(
                {
                    "id": f"page:{name[:-5]}#{i}",
                    "kind": "page",
                    "title": f"{label} · {first}",
                    "text": body[:3000],
                    "url": path,
                }
            )
    return docs


# ── 동적 콘텐츠 ────────────────────────────────────────────────────────────────


def _from_db() -> dict | None:
    try:
        from system.db import (
            admission_faq_db,
            gallery_db,
            members_db,
            news_db,
            papers_db,
            popup_db,
        )

        def rows(col):
            return [
                {k: v for k, v in d.items() if k != "_id"}
                for d in col.find({}, {"_id": 0}).limit(2000)
            ]

        papers = rows(papers_db)
        by_year: dict = {}
        for p in papers:
            by_year.setdefault(p.get("year"), []).append(p)
        return {
            "members": rows(members_db),
            "news": rows(news_db),
            "papers": [{"year": y, "papers": ps} for y, ps in by_year.items()],
            "faq": rows(admission_faq_db),
            "gallery": rows(gallery_db),
            "popups": rows(popup_db),
        }
    except Exception as e:
        logger.info("홈페이지 DB 대신 공개 API를 씁니다: %s", e)
        return None


def _from_api() -> dict:
    base = homepage_api_base()
    out = {}
    with httpx.Client(timeout=15.0, follow_redirects=True) as client:
        for key, path in (
            ("members", "members"),
            ("news", "news"),
            ("papers", "papers"),
            ("faq", "faq"),
            ("gallery", "gallery"),
            ("popups", "popups"),
        ):
            try:
                r = client.get(f"{base}/api/{path}/")
                out[key] = r.json() if r.status_code == 200 else []
            except Exception as e:
                logger.warning("홈페이지 %s 를 읽지 못했습니다: %s", key, e)
                out[key] = []
    return out


def _strip_html(value) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _list_text(value) -> str:
    if isinstance(value, list):
        return "\n".join(f"- {_strip_html(v)}" for v in value if v)
    return _strip_html(value)


def _dynamic_docs(data: dict) -> list[dict]:
    docs = []
    for m in data.get("members") or []:
        if not isinstance(m, dict) or not m.get("name"):
            continue
        parts = [
            f"이름: {m.get('name')}",
            f"구분: {m.get('section') or ''} / 직위: {m.get('position') or ''}",
            f"소속: {m.get('affiliation') or ''}",
        ]
        if m.get("email"):
            parts.append(f"이메일: {m['email']}")
        for key in ("연구", "학력", "경력", "수상"):
            if m.get(key):
                parts.append(f"{key}:\n{_list_text(m[key])}")
        docs.append(
            {
                "id": f"member:{m.get('uid') or m.get('name')}",
                "kind": "member",
                "title": f"구성원 · {m.get('name')} ({m.get('position') or m.get('section') or ''})",
                "text": "\n".join(parts),
                "url": "/people",
                "meta": {
                    "name": m.get("name"),
                    "section": m.get("section"),
                    "position": m.get("position"),
                },
            }
        )
    for n in data.get("news") or []:
        if isinstance(n, dict) and n.get("title"):
            docs.append(
                {
                    "id": f"news:{n.get('uid') or n.get('title')}",
                    "kind": "news",
                    "title": f"소식 · {n.get('title')} ({n.get('date') or ''})",
                    "text": f"{n.get('title')}\n날짜: {n.get('date') or ''}\n{_strip_html(n.get('content'))[:2500]}"
                    + (f"\n링크: {n['url']}" if n.get("url") else ""),
                    "url": "/news",
                    "meta": {"date": n.get("date")},
                }
            )
    for group in data.get("papers") or []:
        year = group.get("year") if isinstance(group, dict) else None
        for p in (group.get("papers") or []) if isinstance(group, dict) else []:
            title = p.get("title") or p.get("name")
            if not title:
                continue
            fields = [f"제목: {title}", f"연도: {year}"]
            for key in (
                "authors",
                "author",
                "journal",
                "venue",
                "publisher",
                "type",
                "doi",
                "link",
                "url",
            ):
                if p.get(key):
                    fields.append(
                        f"{key}: {_strip_html(p[key]) if not isinstance(p[key], list) else ', '.join(map(str, p[key]))}"
                    )
            docs.append(
                {
                    "id": f"paper:{p.get('uid') or title[:60]}",
                    "kind": "paper",
                    "title": f"논문 · {title[:90]} ({year})",
                    "text": "\n".join(fields),
                    "url": "/publications",
                    "meta": {"year": year},
                }
            )
    for f in data.get("faq") or []:
        if isinstance(f, dict) and f.get("question"):
            docs.append(
                {
                    "id": f"faq:{f.get('uid') or f.get('question')[:40]}",
                    "kind": "faq",
                    "title": f"입학 FAQ · {f.get('question')}",
                    "text": f"[{f.get('category') or ''}] Q. {f.get('question')}\nA. {_strip_html(f.get('answer'))}",
                    "url": "/admission",
                }
            )
    for g in data.get("gallery") or []:
        if isinstance(g, dict) and g.get("title"):
            docs.append(
                {
                    "id": f"gallery:{g.get('uid') or g.get('title')}",
                    "kind": "gallery",
                    "title": f"갤러리 · {g.get('title')} ({g.get('date') or ''})",
                    "text": f"{g.get('title')}\n날짜: {g.get('date') or ''}\n{_strip_html(g.get('content'))[:1500]}",
                    "url": "/gallery",
                }
            )
    for p in data.get("popups") or []:
        if isinstance(p, dict) and p.get("title") and p.get("is_active", True):
            docs.append(
                {
                    "id": f"notice:{p.get('uid') or p.get('title')}",
                    "kind": "notice",
                    "title": f"공지 · {p.get('title')}",
                    "text": f"{p.get('title')}\n게시 기간: {p.get('start_date') or ''} ~ {p.get('end_date') or ''}\n{_strip_html(p.get('content'))[:1500]}"
                    + (f"\n링크: {p['link_url']}" if p.get("link_url") else ""),
                    "url": "/",
                }
            )
    return docs


class _Cache:
    def __init__(self):
        self.lock = threading.Lock()
        self.at = 0.0
        self.docs: list[dict] = []
        self.index: BM25 | None = None
        self.source = ""

    def get(self) -> tuple[list[dict], BM25]:
        with self.lock:
            if self.index is None or time.time() - self.at > HOMEPAGE_CACHE_S:
                data = _from_db()
                self.source = "db"
                if data is None:
                    data = _from_api()
                    self.source = "api"
                docs = _page_docs() + _dynamic_docs(data)
                self.docs, self.index, self.at = docs, BM25(docs), time.time()
            return self.docs, self.index


_cache = _Cache()


def documents() -> list[dict]:
    return _cache.get()[0]


def search(query: str, kind: str | None = None, limit: int = 8) -> list[dict]:
    docs, index = _cache.get()
    hits = index.search(
        query, limit=limit, where=(lambda d: d["kind"] == kind) if kind else None
    )
    return [
        {
            "id": d["id"],
            "kind": d["kind"],
            "title": d["title"],
            "url": d["url"],
            "snippet": d["text"][:260].replace("\n", " "),
            "score": round(s, 2),
        }
        for s, d in hits
    ]


def read(doc_id: str) -> dict | None:
    for d in documents():
        if d["id"] == doc_id:
            return {
                "id": d["id"],
                "title": d["title"],
                "url": d["url"],
                "text": d["text"],
            }
    return None


def list_members(section: str = "", query: str = "") -> list[dict]:
    out = []
    for d in documents():
        if d["kind"] != "member":
            continue
        meta = d.get("meta") or {}
        if section and section not in f"{meta.get('section')} {meta.get('position')}":
            continue
        if query and query not in d["text"]:
            continue
        out.append(
            {
                "id": d["id"],
                "name": meta.get("name"),
                "section": meta.get("section"),
                "position": meta.get("position"),
            }
        )
    return out


def list_publications(year: str = "", query: str = "") -> dict:
    items = []
    for d in documents():
        if d["kind"] != "paper":
            continue
        if year and str((d.get("meta") or {}).get("year")) != str(year):
            continue
        if query and query.lower() not in d["text"].lower():
            continue
        items.append({"id": d["id"], "title": d["title"]})
    by_year: dict = {}
    for d in documents():
        if d["kind"] == "paper":
            y = str((d.get("meta") or {}).get("year"))
            by_year[y] = by_year.get(y, 0) + 1
    # 건수는 코드가 센다(모델이 목록을 눈으로 세지 않게)
    return {
        "count": len(items),
        "count_by_year": dict(sorted(by_year.items(), reverse=True)),
        "items": items[:40],
        "truncated": len(items) > 40,
    }


def overview() -> dict:
    """무엇을 알고 있는지 한눈에 — 모델이 어떤 도구를 쓸지 고르는 데 쓴다."""
    docs = documents()
    kinds: dict = {}
    for d in docs:
        kinds[d["kind"]] = kinds.get(d["kind"], 0) + 1
    return {
        "source": _cache.source,
        "documents": kinds,
        "pages": [f"{v[1]} ({v[0]})" for v in PAGES.values()],
    }
