"""홈페이지 정보 도구 (홈페이지 안내 · 구성원용 공통)."""

from .. import homepage_kb
from ..registry import tool

_KINDS = "page/member/paper/news/faq/gallery/notice"


@tool(
    "site_overview",
    "홈페이지가 가진 정보 종류와 건수",
    label="홈페이지 정보 개요",
    cache_s=300,
)
def site_overview(ctx):
    return homepage_kb.overview()


@tool(
    "search_site",
    f"홈페이지 전체(페이지·구성원·논문·소식·입학 FAQ·갤러리·공지) 검색. kind 로 좁힐 수 있음({_KINDS})",
    {"query": "검색어", "kind": "(선택) 문서 종류"},
    label="홈페이지 검색 · {query}",
    cache_s=300,
)
def search_site(ctx, query="", kind=""):
    hits = homepage_kb.search(str(query), kind=str(kind) or None)
    if not hits:
        return {
            "count": 0,
            "note": "결과 없음. 더 짧은 핵심어로 다시 찾거나 kind 를 빼 보시기 바랍니다.",
        }
    return {"count": len(hits), "results": hits}


@tool(
    "read_doc",
    "검색·목록 결과의 문서 전문 읽기",
    {"id": "문서 id"},
    label="문서 읽기 · {id}",
    cache_s=300,
    reads=True,
)
def read_doc(ctx, id=""):
    doc = homepage_kb.read(str(id))
    if not doc:
        raise ValueError(
            "없는 문서 id 입니다. search_site 결과의 id 를 그대로 작성해 주시기 바랍니다."
        )
    return doc


@tool(
    "list_members",
    "구성원 목록(구분·직위로 거르기)",
    {
        "section": "(선택) 예: 교수, 대학원 과정, 박사과정",
        "query": "(선택) 이름·연구주제",
    },
    label="구성원 목록 확인",
    cache_s=300,
)
def list_members(ctx, section="", query=""):
    items = homepage_kb.list_members(str(section), str(query))
    return {"count": len(items), "members": items}


@tool(
    "list_publications",
    "논문 목록과 연도별 건수(코드가 센 값)",
    {"year": "(선택) 연도", "query": "(선택) 제목 키워드"},
    label="논문 목록 · {year}{query}",
    cache_s=300,
)
def list_publications(ctx, year="", query=""):
    return homepage_kb.list_publications(str(year), str(query))


@tool(
    "list_docs",
    "종류별 문서 목록을 최신순으로(소식·공지·입학 FAQ·갤러리 등). '최근 소식', 'FAQ 전부'처럼 검색어 없이 훑을 때 쓴다",
    {
        "kind": "news/notice/faq/gallery/page 중 하나",
        "query": "(선택) 제목·본문 키워드",
        "limit": "(선택) 개수(기본 15, 최대 40)",
    },
    label="목록 보기 · {kind}",
    cache_s=300,
)
def list_docs(ctx, kind="", query="", limit=""):
    kind = str(kind).strip()
    if kind not in ("news", "notice", "faq", "gallery", "page", "paper", "member"):
        raise ValueError("kind 는 news/notice/faq/gallery/page 중 하나여야 합니다.")
    q = str(query).lower()
    docs = [
        d
        for d in homepage_kb.documents()
        if d["kind"] == kind and (not q or q in f"{d['title']} {d['text']}".lower())
    ]
    docs.sort(key=lambda d: str((d.get("meta") or {}).get("date") or ""), reverse=True)
    try:
        n = max(1, min(40, int(limit or 15)))
    except (TypeError, ValueError):
        n = 15
    return {
        "count": len(docs),  # 전체 건수는 코드가 센다
        "shown": min(n, len(docs)),
        "results": [
            {
                "id": d["id"],
                "title": d["title"],
                "date": (d.get("meta") or {}).get("date"),
                "url": d["url"],
                "snippet": d["text"][:160].replace("\n", " "),
            }
            for d in docs[:n]
        ],
    }
