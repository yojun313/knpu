"""챗봇 도구 — 모델은 아래 도구를 JSON 한 줄로 요청하고, 서버가 실행해 결과를 돌려준다.

도구 결과에는 건수 · 줄 범위처럼 셀 수 있는 값을 코드가 미리 계산해 싣는다(모델이 목록을 세지 않게).
"""

import json
from pathlib import Path

from . import code_kb, homepage_kb
from .config import REPO_ROOT

# 서비스 안내: 코드 위치 · 설명서 · 주소. 모델이 어디부터 볼지 정하는 지도 역할.
SERVICES = [
    {
        "key": "homepage",
        "name": "연구실 홈페이지 (FPEI)",
        "code": "homepage/server",
        "does": "연구원 소개·구성원·논문·소식·갤러리·입학 안내, 통합 로그인(회원가입·이메일 인증·패스키)과 관리자 편집 화면",
    },
    {
        "key": "manager",
        "name": "MANAGER",
        "code": "manager/server",
        "manuals": [
            "manager/server/app/public/manager.html",
            "manager/server/app/public/manuals/",
        ],
        "does": "연구 리소스 관리·빅데이터 분석 데스크톱 앱의 서버·다운로드·문서 페이지, LLM 프록시(/llm)",
    },
    {
        "key": "progress",
        "name": "MANAGER Web (진행 상황)",
        "code": "manager/web",
        "does": "MANAGER 작업 진행 상황 웹",
    },
    {
        "key": "crawler",
        "name": "CRAWLER",
        "code": "crawler",
        "does": "네이버 뉴스·카페, 유튜브 등 수집 작업 생성·큐·데이터베이스 관리",
    },
    {
        "key": "network",
        "name": "NETWORK",
        "code": "network",
        "manuals": ["network/app/static/manual.html"],
        "does": "텍스트 속 단어·행위자 네트워크 분석과 시각화(vis-network), 커뮤니티 탐지, AI 해석",
    },
    {
        "key": "statistics",
        "name": "STATISTICS",
        "code": "statistics",
        "manuals": ["statistics/app/static/manual.html"],
        "does": "크롤링 데이터 통계 분석(기술통계·상관·회귀·t검정/ANOVA·교차분석·군집·PCA 등), 표·차트, AI 통계 분석 사이드바",
    },
    {
        "key": "kemkim",
        "name": "KEMKIM",
        "code": "kemkim",
        "manuals": ["kemkim/app/static/manual.html"],
        "does": "KEM(DoV)·KIM(DoD) 미래신호 분석: 강한/약한/잠재/알려진 신호 사분면, 신호 추적, 단어별·그룹 AI 해석",
    },
    {
        "key": "mcdm",
        "name": "POLYDECISION",
        "code": "mcdm",
        "does": "AHP 다기준 의사결정: 계층 설계·설문 배포·응답 수집·일관성 검사·가중치 분석",
    },
    {
        "key": "whisper",
        "name": "WHISPER",
        "code": "whisper",
        "does": "음성·영상 파일 STT 노트: GPU 서버 전사, 진행률, 구간 재생·검색·내보내기",
    },
    {
        "key": "dashboard",
        "name": "관리자 대시보드",
        "code": "admin",
        "does": "PM2 프로세스·서버 자원·로그·사용자·Git·ecosystem·nginx·포트 관리 (관리자 전용)",
    },
    {
        "key": "complaint",
        "name": "AI 고소장 생성 서비스",
        "code": "complaint/server",
        "does": "AI 상담으로 고소 사실을 정리하고 법령·판례(RAG)를 근거로 고소장 초안(docx/pdf) 생성",
    },
    {
        "key": "system",
        "name": "공통 모듈 (system)",
        "code": "system",
        "does": "로그인/세션(auth), DB 연결(db), LLM 클라이언트와 사용자별 LLM 설정(llm), 공용 UI·테마(ui, shared_ui.py), 서비스 주소(endpoints·services.json), 챗봇(chatbot)",
    },
]


def _domains() -> dict:
    try:
        cfg = json.loads((REPO_ROOT / "services.json").read_text(encoding="utf-8"))
        return {
            k: f"https://{v['prod_domain']}{v.get('public_path', '')}"
            for k, v in cfg["services"].items()
        }
    except Exception:
        return {}


def list_services() -> dict:
    domains = _domains()
    return {
        "count": len(SERVICES),
        "services": [{**s, "url": domains.get(s["key"])} for s in SERVICES],
    }


# ── 도구 정의 (프롬프트에 그대로 들어가는 설명) ─────────────────────────────────

PUBLIC_TOOLS = {
    "site_overview": ("홈페이지가 가진 정보 종류와 건수", {}),
    "search_site": (
        "홈페이지 전체(페이지·구성원·논문·소식·입학 FAQ·갤러리·공지) 검색. kind 로 좁힐 수 있음(page/member/paper/news/faq/gallery/notice)",
        {"query": "검색어", "kind": "(선택) 문서 종류"},
    ),
    "read_doc": ("검색 결과의 문서 전문 읽기", {"id": "문서 id"}),
    "list_members": (
        "구성원 목록(구분·직위로 거르기)",
        {
            "section": "(선택) 예: 교수, 대학원 과정, 박사과정",
            "query": "(선택) 이름·연구주제",
        },
    ),
    "list_publications": (
        "논문 목록과 연도별 건수(코드가 센 값)",
        {"year": "(선택) 연도", "query": "(선택) 제목 키워드"},
    ),
}

MEMBER_TOOLS = {
    "list_services": (
        "연구실 소프트웨어 목록: 하는 일·코드 폴더·설명서·주소. 무엇부터 볼지 모를 때 먼저 부른다",
        {},
    ),
    "search_code": (
        "저장소 코드·설명서 키워드 검색(경로·줄 번호와 발췌를 돌려줌)",
        {
            "query": "검색어(기능 이름·화면 문구·함수명)",
            "path": "(선택) 폴더로 좁히기 예: kemkim/",
        },
    ),
    "grep": (
        "정확한 문자열/정규식 검색(함수·라우트·설정 키 찾기). 전체 일치 파일 수를 함께 돌려줌",
        {"pattern": "문자열 또는 정규식", "path": "(선택) 폴더"},
    ),
    "read_file": (
        "파일 일부 읽기(최대 220줄, 줄 번호 포함)",
        {"path": "저장소 기준 경로", "start": "시작 줄(기본 1)", "end": "(선택) 끝 줄"},
    ),
    "list_dir": (
        "폴더 안의 하위 폴더·파일 목록",
        {"path": "저장소 기준 폴더(비우면 루트)"},
    ),
    **PUBLIC_TOOLS,
}


def tool_prompt(tools: dict) -> str:
    lines = []
    for name, (desc, args) in tools.items():
        arg = ", ".join(f'"{k}": {v}' for k, v in args.items())
        lines.append(f"- {name}({arg}) — {desc}")
    return "\n".join(lines)


def run(mode: str, name: str, args: dict) -> dict:
    allowed = MEMBER_TOOLS if mode == "member" else PUBLIC_TOOLS
    if name not in allowed:
        return {
            "error": f"사용할 수 없는 도구입니다: {name}. 가능한 도구: {', '.join(allowed)}"
        }
    known = set(allowed[name][1])
    extra = set(args) - known
    if extra:
        # 모르는 인자를 조용히 무시하면 엉뚱한 결과를 받게 되므로 오류로 알린다(dis-047 교훈)
        return {
            "error": f"{name} 에 없는 인자: {', '.join(sorted(extra))}. 가능한 인자: {', '.join(known) or '없음'}"
        }
    a = {k: (v if v is not None else "") for k, v in args.items()}
    try:
        if name == "site_overview":
            return homepage_kb.overview()
        if name == "search_site":
            hits = homepage_kb.search(
                str(a.get("query", "")), kind=a.get("kind") or None
            )
            return (
                {"count": len(hits), "results": hits}
                if hits
                else {
                    "count": 0,
                    "note": "결과 없음. 더 짧은 핵심어로 다시 찾거나 kind 를 빼 보세요.",
                }
            )
        if name == "read_doc":
            doc = homepage_kb.read(str(a.get("id", "")))
            return doc or {
                "error": "없는 문서 id 입니다. search_site 결과의 id 를 그대로 쓰세요."
            }
        if name == "list_members":
            items = homepage_kb.list_members(
                str(a.get("section", "")), str(a.get("query", ""))
            )
            return {"count": len(items), "members": items}
        if name == "list_publications":
            return homepage_kb.list_publications(
                str(a.get("year", "")), str(a.get("query", ""))
            )
        if name == "list_services":
            return list_services()
        if name == "search_code":
            hits = code_kb.index.search(str(a.get("query", "")), str(a.get("path", "")))
            if not hits:
                return {
                    "count": 0,
                    "note": "결과 없음. 화면에 보이는 문구나 영어 함수명으로 바꿔 찾거나 grep 을 써 보세요.",
                }
            return {"count": len(hits), "results": hits}
        if name == "grep":
            return code_kb.grep(str(a.get("pattern", "")), str(a.get("path", "")))
        if name == "read_file":
            end = a.get("end")
            return code_kb.read_file(
                str(a.get("path", "")),
                int(a.get("start") or 1),
                int(end) if str(end).strip() else None,
            )
        if name == "list_dir":
            return code_kb.list_dir(str(a.get("path", "")))
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:  # 도구 하나가 실패해도 대화는 이어간다
        return {"error": f"{type(e).__name__}: {e}"}
    return {"error": "알 수 없는 도구"}


def sources_from(name: str, args: dict, result: dict) -> list[dict]:
    """실제로 읽은 근거만 출처로 모은다(검색 목록만 본 것은 출처가 아니다)."""
    if not isinstance(result, dict) or result.get("error"):
        return []
    if name == "read_doc":
        return [
            {
                "type": "page",
                "id": result.get("id"),
                "title": result.get("title"),
                "url": result.get("url"),
            }
        ]
    if name == "read_file":
        return [
            {"type": "code", "path": result.get("path"), "lines": result.get("lines")}
        ]
    return []


def seen_refs(name: str, result: dict) -> set[str]:
    """답변에 인용해도 되는 경로 · 문서 id (검색 결과에 나온 것 포함)."""
    refs: set[str] = set()
    if not isinstance(result, dict):
        return refs
    for key in ("results", "hits"):
        for r in result.get(key) or []:
            if r.get("path"):
                refs.add(r["path"])
            if r.get("id"):
                refs.add(r["id"])
    if result.get("path"):
        refs.add(result["path"])
    if result.get("id"):
        refs.add(result["id"])
    for s in result.get("services") or []:
        if s.get("code"):
            refs.add(s["code"])
        for m in s.get("manuals") or []:
            refs.add(m)
    base = result.get("path")
    if name == "list_dir" and base:
        for f in result.get("files") or []:
            refs.add(str(Path(base) / f) if base != "." else f)
    return refs
