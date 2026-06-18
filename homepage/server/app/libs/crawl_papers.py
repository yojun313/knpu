"""
fetch_bib.py — 논문 제목과 등재 종류(SCI/SCOPUS/KCI)로 메타데이터 수집

단독 실행:
  python fetch_bib.py "논문 제목" --type SCI
  python fetch_bib.py "논문 제목" --type KCI
  python fetch_bib.py --test homepage.papers.json   # 전체 테스트

다른 프로그램에서 임포트:
  from fetch_bib import fetch_bib, load_name_map
  name_map = load_name_map("author_names.json")
  record = fetch_bib("Effect of Fukushima...", "SCI", name_map)
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

import bibtexparser
import requests
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CROSSREF_URL = "https://api.crossref.org/works"
CONFIDENCE_THRESHOLD = 0.60
KCI_SEARCH_URL = "https://www.kci.go.kr/kciportal/po/search/poTotalSearList.kci"
KCI_DETAIL_URL = (
    "https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci"
)
KCI_TITLE_THRESHOLD = 0.55

BIBTEX_TYPE_MAP: dict[str, str] = {
    "article": "journal",
    "inproceedings": "conference",
    "conference": "conference",
    "proceedings": "conference",
    "book": "book_chapter",
    "incollection": "book_chapter",
    "techreport": "report",
    "report": "report",
}

CROSSREF_HEADERS = {"User-Agent": "fetch_bib/1.0 (academic; mailto:research@lab.kr)"}
KCI_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}

# ---------------------------------------------------------------------------
# Author name map
# ---------------------------------------------------------------------------


def load_name_map(path: str | Path = "author_names.json") -> dict[str, str]:
    """author_names.json → {영문변형(소문자): 한국어이름} 딕셔너리."""
    p = Path(path)
    if not p.exists():
        return {}
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    result: dict[str, str] = {}
    for entry in data.get("mappings", []):
        kr = entry.get("kr")
        if not kr:
            continue
        for en in entry.get("en", []):
            result[en.strip().lower()] = kr
    return result


def resolve_authors_kr(
    authors: list[str], name_map: dict[str, str]
) -> list[str | None]:
    return [name_map.get(a.strip().lower()) for a in authors]


# ---------------------------------------------------------------------------
# Language / text utilities
# ---------------------------------------------------------------------------


def detect_language(title: str) -> str:
    for ch in title:
        if "가" <= ch <= "힣":
            return "ko"
    return "en"


def _is_korean(text: str) -> bool:
    return any("가" <= ch <= "힣" for ch in text)


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _strip_braces(text: str) -> str:
    return re.sub(r"[{}]", "", text).strip()


def _strip_tags(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text)).strip()


# ---------------------------------------------------------------------------
# APA citation builder
# ---------------------------------------------------------------------------


def generate_apa(record: dict) -> str:
    authors = record.get("authors") or []
    year = record.get("year") or "n.d."
    title = record.get("title") or ""
    venue = record.get("venue") or ""
    volume = record.get("volume") or ""
    issue = record.get("issue") or ""
    pages = record.get("pages") or ""
    doi = record.get("doi") or ""
    pub_type = record.get("publication_type", "other")

    if not authors:
        author_str = "Anonymous"
    elif len(authors) == 1:
        author_str = authors[0]
    elif len(authors) <= 20:
        author_str = ", ".join(authors[:-1]) + ", & " + authors[-1]
    else:
        author_str = ", ".join(authors[:19]) + ", ... " + authors[-1]

    doi_str = f" https://doi.org/{doi}" if doi else ""

    if pub_type == "journal":
        vol_issue = f", {volume}" if volume else ""
        if issue:
            vol_issue += f"({issue})"
        pages_str = f", {pages}" if pages else ""
        return (
            f"{author_str} ({year}). {title}. {venue}{vol_issue}{pages_str}.{doi_str}"
        )
    elif pub_type == "conference":
        pages_str = f" (pp. {pages})" if pages else ""
        pub = record.get("publisher") or ""
        pub_str = f" {pub}." if pub else ""
        return f"{author_str} ({year}). {title}. In Proceedings of {venue}{pages_str}.{pub_str}{doi_str}"
    else:
        return f"{author_str} ({year}). {title}. {venue}.{doi_str}"


# ---------------------------------------------------------------------------
# BibTeX parsing (KCI bibtex format)
# ---------------------------------------------------------------------------


def _parse_bibtex_text(text: str) -> list[dict]:
    parser = BibTexParser(common_strings=True)
    parser.customization = convert_to_unicode  # type: ignore[attr-defined]
    db = bibtexparser.loads(text, parser=parser)
    return db.entries


def _parse_bibtex_authors(raw: str) -> list[str]:
    if not raw:
        return []
    parts = [p.strip() for p in re.split(r"\s+and\s+", raw, flags=re.IGNORECASE)]
    result = []
    for part in parts:
        if not part:
            continue
        if "," in part:
            result.append(part.strip())
        else:
            tokens = part.split()
            if len(tokens) >= 2:
                result.append(f"{tokens[-1]}, {' '.join(tokens[:-1])}")
            else:
                result.append(part)
    return result


def _build_record_from_bibtex(
    entry: dict, name_map: dict[str, str], journal_type: str
) -> dict:
    """BibTeX entry → final.json 호환 레코드."""
    now = datetime.now(timezone.utc).isoformat()
    entry_type = entry.get("ENTRYTYPE", "misc").lower()
    pub_type = BIBTEX_TYPE_MAP.get(entry_type, "other")

    title = _strip_braces(entry.get("title", ""))
    authors = _parse_bibtex_authors(_strip_braces(entry.get("author", "")))
    venue = (
        _strip_braces(entry.get("journal", ""))
        or _strip_braces(entry.get("booktitle", ""))
        or _strip_braces(entry.get("series", ""))
        or None
    )

    year_raw = entry.get("year", "")
    try:
        year = int(re.sub(r"\D", "", str(year_raw))) if year_raw else None
    except ValueError:
        year = None

    # published_date: month 필드에서 보완 (BibTeX에 month가 있을 경우)
    month_map = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
    }
    month_raw = _strip_braces(entry.get("month", ""))
    month_num = month_map.get(month_raw.lower()) if month_raw else None
    if not month_num and month_raw:
        try:
            month_num = int(month_raw)
        except ValueError:
            pass
    if year and month_num:
        published_date: str | None = f"{year:04d}-{month_num:02d}"
    elif year:
        published_date = str(year)
    else:
        published_date = None

    doi_raw = _strip_braces(entry.get("doi", ""))
    for prefix in (
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
    ):
        if doi_raw.startswith(prefix):
            doi_raw = doi_raw[len(prefix) :]
            break
    doi = doi_raw or None
    url_raw = _strip_braces(entry.get("url", ""))
    url = url_raw or (f"https://doi.org/{doi}" if doi else None)

    keywords_raw = _strip_braces(entry.get("keywords", ""))
    keywords = (
        [k.strip() for k in re.split(r"[,;]", keywords_raw) if k.strip()]
        if keywords_raw
        else None
    )

    record = {
        "uid": str(uuid.uuid4()),
        "title": title,
        "authors": authors,
        "authors_kr": resolve_authors_kr(authors, name_map),
        "year": year,
        "published_date": published_date,
        "publication_type": pub_type,
        "journal_type": journal_type,
        "venue": venue,
        "volume": _strip_braces(entry.get("volume", "")) or None,
        "issue": _strip_braces(entry.get("number", "")) or None,
        "pages": _strip_braces(entry.get("pages", "")).replace("--", "-") or None,
        "publisher": _strip_braces(entry.get("publisher", "")) or None,
        "doi": doi,
        "url": url,
        "abstract": _strip_braces(entry.get("abstract", "")) or None,
        "language": detect_language(title),
        "apa_citation": None,
        "keywords": keywords,
        "source_api": "bibtex",
        "api_confidence": 1.0,
        "fetched_at": now,
        "verified": False,
        "notes": "",
    }
    record["apa_citation"] = generate_apa(record)
    return record


# ---------------------------------------------------------------------------
# CrossRef (SCI / SCOPUS)
# ---------------------------------------------------------------------------


def _crossref_query(query: str, rows: int = 5) -> list[dict]:
    params = {
        "query": f'title="{query}"',
        "rows": rows,
        "select": "title,author,issued,container-title,DOI,type,volume,issue,page,publisher,abstract",
    }
    try:
        resp = requests.get(
            CROSSREF_URL, params=params, headers=CROSSREF_HEADERS, timeout=15
        )
        resp.raise_for_status()
        return resp.json().get("message", {}).get("items", [])
    except Exception as e:
        print(f"  [CrossRef] 오류: {e}")
        return []


def _best_crossref_match(
    input_title: str,
    items: list[dict],
    known_names: set[str],
    korean: bool,
) -> dict | None:
    if not items:
        return None

    if korean:
        # KCI 논문은 CrossRef에 영문 제목으로 등록 → 알려진 저자 기반 신뢰
        for item in items:
            for a in item.get("author", []):
                given = a.get("given", "")
                family = a.get("family", "")
                full = f"{family}, {given}".strip(", ").lower()
                full2 = f"{given} {family}".strip().lower()
                if full in known_names or full2 in known_names:
                    item["_confidence"] = 0.8
                    item["_source"] = "crossref"
                    return item
        return None

    # 영문 제목: 유사도 체크
    best, best_score = None, 0.0
    for item in items:
        titles = item.get("title", [])
        returned = titles[0] if titles else ""
        score = _similarity(input_title, returned)
        if score > best_score:
            best_score = score
            best = item
    if best and best_score >= CONFIDENCE_THRESHOLD:
        best["_confidence"] = best_score
        best["_source"] = "crossref"
        return best
    return None


def _build_record_from_crossref(
    title: str,
    raw: dict,
    name_map: dict[str, str],
    journal_type: str,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()

    # 저자
    authors: list[str] = []
    for a in raw.get("author", []):
        given = a.get("given", "")
        family = a.get("family", "")
        if family:
            authors.append(f"{family}, {given}".strip(", "))

    # DOI / URL
    doi = raw.get("DOI") or None
    url = f"https://doi.org/{doi}" if doi else None

    # 제목
    api_title = raw.get("title", [])
    api_title = api_title[0] if isinstance(api_title, list) and api_title else title

    # 날짜
    parts = raw.get("issued", {}).get("date-parts", [[]])
    p = [x for x in (parts[0] if parts else []) if x is not None]
    if len(p) >= 3:
        published_date: str | None = f"{p[0]:04d}-{p[1]:02d}-{p[2]:02d}"
    elif len(p) == 2:
        published_date = f"{p[0]:04d}-{p[1]:02d}"
    elif len(p) == 1:
        published_date = str(p[0])
    else:
        published_date = None
    year = p[0] if p else None

    # 타입
    type_map = {
        "journal-article": "journal",
        "proceedings-article": "conference",
        "book-chapter": "book_chapter",
        "report": "report",
    }
    pub_type = type_map.get(raw.get("type", ""), "other")

    venue = (raw.get("container-title") or [None])[0]

    record = {
        "uid": str(uuid.uuid4()),
        "title": api_title,
        "authors": authors,
        "authors_kr": resolve_authors_kr(authors, name_map),
        "year": year,
        "published_date": published_date,
        "publication_type": pub_type,
        "journal_type": journal_type,
        "venue": venue,
        "volume": raw.get("volume"),
        "issue": raw.get("issue"),
        "pages": raw.get("page"),
        "publisher": raw.get("publisher"),
        "doi": doi,
        "url": url,
        "abstract": raw.get("abstract"),
        "language": detect_language(api_title),
        "apa_citation": None,
        "keywords": None,
        "source_api": "crossref",
        "api_confidence": round(raw.get("_confidence", 0.0), 4),
        "fetched_at": now,
        "verified": False,
        "notes": "",
    }
    record["apa_citation"] = generate_apa(record)
    return record


def _fetch_crossref(
    title: str,
    name_map: dict[str, str],
    journal_type: str,
) -> dict | None:
    known_names = set(name_map.keys())
    korean = _is_korean(title)

    # 1차: 전체 제목
    items = _crossref_query(title)
    raw = _best_crossref_match(title, items, known_names, korean)

    # 2차: 콜론 앞 핵심어
    if raw is None:
        short = title.split(":")[0].strip()
        if short and short != title:
            items2 = _crossref_query(short)
            raw = _best_crossref_match(title, items2, known_names, korean)

    if raw is None:
        print(f"  [CrossRef] 매칭 실패")
        return None

    return _build_record_from_crossref(title, raw, name_map, journal_type)


# ---------------------------------------------------------------------------
# KCI web scraping
# ---------------------------------------------------------------------------


def _kci_search_html(title: str) -> str:
    resp = requests.post(
        KCI_SEARCH_URL,
        headers={
            **KCI_HEADERS,
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://www.kci.go.kr",
            "Referer": KCI_SEARCH_URL,
        },
        data={"poSearchBean.keywordList": title, "poSearchBean.searType": "all"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.text


def _extract_art_and_month(
    search_html: str, query: str
) -> tuple[str | None, str | None]:
    soup = BeautifulSoup(search_html, "html.parser")
    best_id, best_date, best_score = None, None, 0.0

    for a_tag in soup.find_all("a", class_="subject"):
        href = a_tag.get("href", "")
        m = re.search(r"artiId=(ART\d{9})", href)
        if not m:
            continue
        art_id = m.group(1)
        result_title = _strip_tags(str(a_tag))
        score = _similarity(query, result_title)
        if score < KCI_TITLE_THRESHOLD:
            continue

        pub_date = None
        parent = a_tag.find_parent()
        for _ in range(5):
            if parent is None:
                break
            info_ul = parent.find("ul", class_="subject-info")
            if info_ul:
                for li in info_ul.find_all("li"):
                    text = li.get_text(strip=True)
                    if re.fullmatch(r"\d{4}\.\d{1,2}", text):
                        y, mo = text.split(".")
                        pub_date = f"{int(y):04d}-{int(mo):02d}"
                        break
                break
            parent = parent.find_parent()

        if score > best_score:
            best_score = score
            best_id = art_id
            best_date = pub_date

    if best_id:
        print(f"  [KCI] ART={best_id} 유사도={best_score:.2f} 게재월={best_date}")
    else:
        print(f"  [KCI] 검색 결과 없음 (threshold={KCI_TITLE_THRESHOLD})")
    return best_id, best_date


def _kci_detail_html(art_id: str) -> str:
    resp = requests.get(
        KCI_DETAIL_URL,
        headers={**KCI_HEADERS, "Referer": KCI_SEARCH_URL},
        params={"sereArticleSearchBean.artiId": art_id},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.text


def _extract_bibtex(detail_html: str) -> str | None:
    soup = BeautifulSoup(detail_html, "html.parser")
    p = soup.find("p", id="BibTex")
    if not p:
        return None
    raw = html_lib.unescape(p.get_text())
    raw = re.sub(r"<br\s*/?>", "\n", raw).strip()
    return raw if raw.startswith("@") else None


def _fetch_kci(
    title: str,
    name_map: dict[str, str],
    journal_type: str,
) -> dict | None:
    try:
        search_html = _kci_search_html(title)
    except requests.RequestException as e:
        print(f"  [KCI] 검색 요청 실패: {e}")
        return None

    art_id, pub_month = _extract_art_and_month(search_html, title)
    if not art_id:
        return None

    time.sleep(0.4)

    try:
        detail_html = _kci_detail_html(art_id)
    except requests.RequestException as e:
        print(f"  [KCI] 상세 요청 실패: {e}")
        return None

    bibtex_text = _extract_bibtex(detail_html)
    if not bibtex_text:
        print(f"  [KCI] BibTeX 추출 실패")
        return None

    entries = _parse_bibtex_text(bibtex_text)
    if not entries:
        print(f"  [KCI] BibTeX 파싱 실패")
        return None

    record = _build_record_from_bibtex(entries[0], name_map, journal_type)

    # BibTeX에 month 없으므로 검색결과의 게재 연월로 덮어씀
    if pub_month:
        record["published_date"] = pub_month

    kci_url = (
        f"https://www.kci.go.kr/kciportal/ci/sereArticleSearch/"
        f"ciSereArtiView.kci?sereArticleSearchBean.artiId={art_id}"
    )
    record["url"] = record.get("url") or kci_url

    return record


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_bib(
    title: str,
    journal_type: str,
    name_map: dict[str, str] | None = None,
) -> dict | None:
    """
    논문 제목과 등재 종류로 메타데이터를 수집하여 final.json 호환 레코드 반환.

    Args:
        title:        논문 제목 (한글 또는 영문)
        journal_type: "SCI", "SCOPUS", "KCI"
        name_map:     load_name_map() 반환값. None이면 author_names.json 자동 로드

    Returns:
        final.json 호환 dict, 또는 None (수집 실패)
    """
    if name_map is None:
        name_map = load_name_map()

    jtype = journal_type.upper()

    if jtype in ("SCI", "SCOPUS"):
        return _fetch_crossref(title, name_map, jtype)
    elif jtype == "KCI":
        return _fetch_kci(title, name_map, jtype)
    else:
        raise ValueError(
            f"journal_type은 SCI / SCOPUS / KCI 중 하나여야 합니다: {journal_type!r}"
        )


# ---------------------------------------------------------------------------
# CLI / test
# ---------------------------------------------------------------------------


def _load_homepage_titles(path: Path) -> list[tuple[str, str]]:
    """homepage.papers.json에서 (title, auto_type) 목록 반환.
    영문 제목 → SCI, 한국어 제목 → KCI.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    result = []
    for bucket in data:
        for paper in bucket.get("papers", []):
            t = paper.get("title", "").strip()
            if not t:
                continue
            jtype = "KCI" if _is_korean(t) else "SCI"
            result.append((t, jtype))
    return result


def _run_test(
    homepage_path: Path,
    name_map: dict,
    limit: int | None,
    output_path: Path | None,
) -> None:
    titles = _load_homepage_titles(homepage_path)
    if limit:
        titles = titles[:limit]

    results: list[dict] = []
    failed: list[str] = []

    for i, (title, jtype) in enumerate(titles, 1):
        print(f"\n[{i}/{len(titles)}] [{jtype}] {title[:70]}")
        record = fetch_bib(title, jtype, name_map)
        if record:
            print(
                f"  → {record['publication_type']} | {record['published_date']} | {record['venue']}"
            )
            results.append(record)
        else:
            print(f"  → 실패")
            failed.append(title)
        time.sleep(0.8)

    print(
        f"\n=== 완료: 성공 {len(results)} / 실패 {len(failed)} / 전체 {len(titles)} ==="
    )

    if failed:
        print("실패 목록:")
        for t in failed:
            print(f"  - {t}")

    if output_path and results:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n[SAVE] {output_path} ({len(results)}편 저장)")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="논문 제목으로 메타데이터 수집")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("title", nargs="?", help="논문 제목")
    group.add_argument(
        "--test", metavar="JSON", help="homepage.papers.json 경로로 일괄 테스트"
    )

    parser.add_argument(
        "--type",
        "-t",
        choices=["SCI", "SCOPUS", "KCI"],
        help="등재 종류 (title 지정 시 필수)",
    )
    parser.add_argument(
        "--names",
        default="author_names.json",
        help="저자 매핑 파일 (기본: author_names.json)",
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="테스트 시 처리할 최대 논문 수"
    )
    parser.add_argument(
        "--output", "-o", default=None, help="결과 저장 파일 (테스트 모드 전용)"
    )
    args = parser.parse_args()

    name_map = load_name_map(args.names)

    if args.test:
        out = Path(args.output) if args.output else None
        _run_test(Path(args.test), name_map, args.limit, out)
    else:
        if not args.type:
            parser.error("논문 제목 지정 시 --type 이 필요합니다")
        record = fetch_bib(args.title, args.type, name_map)
        if record is None:
            print("[ERROR] 레코드 생성 실패")
            sys.exit(1)
        print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
