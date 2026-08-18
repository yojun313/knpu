"""오프라인 응답 CSV의 가져오기/내보내기가 공유하는 열 구조.

PLAN.md 6.4: "인쇄 레이아웃과 CSV 열 구조를 1:1로 맞춘다 — 어긋나면 반입 때마다
손으로 매핑해야 한다." 그래서 가져오기(entry_routes)와 내보내기(export_routes)가
같은 이 파일을 참조해 열 이름과 값 표기가 절대 어긋나지 않게 한다.

값은 소수(0.333)와 분수(1/3) 표기를 둘 다 받는다 — 종이 설문에 흔히 분수로
적혀 있기 때문이다.
"""

from __future__ import annotations

from fractions import Fraction

CSV_COLUMNS = ["respondent", "parent", "item_a", "item_b", "value"]


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
