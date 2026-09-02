"""오프라인 응답 CSV의 열 구조·값 표기.

- **반입(entry_routes.import_csv)**: wide 형식 — 첫 열이 `respondent`, 이후 열마다
  비교쌍 하나(`Q1. 부모: A vs B`). 응답자 한 명이 한 행이라 이름을 반복 입력하지
  않는다. 열 순서는 설문지 매트릭스의 i<j 쌍 전역 순서이며, 반입 양식 생성
  (export_routes.export_import_template_csv)·인쇄 설문지(print.js)가 같은 순서를 쓴다.
- **내보내기(export_routes.export_responses_csv, sheet_export)**: long(tidy) 형식
  `CSV_COLUMNS` — 분석·재현 패키지 용도라 그대로 둔다. 반입 소스로는 쓰지 않는다.

값은 소수(0.333)와 분수(1/3) 표기를 둘 다 받는다 — 종이 설문에 흔히 분수로
적혀 있기 때문이다.
"""

from __future__ import annotations

from fractions import Fraction

# long(tidy) 내보내기 전용 열. 반입은 wide 형식이라 이 목록을 쓰지 않는다.
CSV_COLUMNS = ["respondent", "parent", "item_a", "item_b", "value"]

# wide 반입 양식의 첫 열 이름.
RESPONDENT_COL = "respondent"


def pair_column_label(n: int, parent: str, name_a: str, name_b: str) -> str:
    """wide 반입 양식의 비교쌍 열 제목. 인쇄 설문지의 문항 번호(Qn)와 1:1로 맞춰
    종이 → CSV 전사 시 열을 바로 찾게 한다. n은 설문지 전체를 통틀어 1부터.
    파싱은 열 위치 기준이므로 이 문자열 자체는 사람이 읽는 용도일 뿐이다."""
    return f"Q{n}. {parent}: {name_a} vs {name_b}"


def parse_value(raw: str) -> float:
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("값이 비어 있습니다")
    if "/" in raw:
        try:
            return float(Fraction(raw))
        except (ValueError, ZeroDivisionError):
            raise ValueError(f"분수 형식이 올바르지 않습니다: {raw!r}")
    try:
        v = float(raw)
    except ValueError:
        raise ValueError(f"숫자로 해석할 수 없습니다: {raw!r}")
    if v <= 0:
        raise ValueError(f"값은 0보다 커야 합니다: {raw!r}")
    return v


def format_value(v: float) -> str:
    """내보낼 때는 사람이 읽기 편한 분수 표기를 우선한다(1/3 등 흔한 값만)."""
    for denom in (2, 3, 4, 5, 6, 7, 8, 9):
        if abs(v - 1 / denom) < 1e-9:
            return f"1/{denom}"
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.4f}".rstrip("0").rstrip(".")
