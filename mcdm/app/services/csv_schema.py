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


def group_item_slots(group: dict) -> list[tuple[str, str]]:
    """이 질문 그룹의 응답 항목(item)을 표시 순서대로 낸다.

    pairwise: `child_uuids` 의 모든 i<j 조합 `(uuid_a, uuid_b)`.
    반입 양식 열 순서·인쇄 설문지 문항 번호·내보내기 열이 전부 이 순서를 공유하므로
    **한 곳에서만** 정의한다. BWM 등 다른 kind 는 여기 분기만 추가하면
    양식/파서/내보내기가 그대로 따라온다.
    """
    kind = group.get("kind", "pairwise")
    cu = group["child_uuids"]
    if kind == "pairwise":
        return [
            (cu[i], cu[j])
            for i in range(len(cu))
            for j in range(i + 1, len(cu))
        ]
    raise ValueError(f"미지원 그룹 kind: {kind!r}")


def group_import_slots(group: dict) -> list[dict]:
    """반입 CSV 에서 이 그룹이 차지하는 열들. 각 원소는 파서가 그대로 쓰는 지시.

    pairwise : {kind:"pairwise", group_id, a, b}  — n(n-1)/2 개
    bwm      : {kind:"pick_best", group_id} {kind:"pick_worst", group_id}
               다음 각 기준마다 {kind:"vector", group_id, item_id:"BO:<c>", crit}
               다음 각 기준마다 {kind:"vector", group_id, item_id:"OW:<c>", crit}
               → 2 + 2n 개 (Best의 BO·Worst의 OW 칸은 잉여지만 양식 규칙성 위해 둔다;
               파서가 채워도 BwmPlugin 이 무시).
    """
    gid = group["group_id"]
    cu = group["child_uuids"]
    kind = group.get("kind", "pairwise")
    if kind == "bwm":
        out = [
            {"kind": "pick_best", "group_id": gid},
            {"kind": "pick_worst", "group_id": gid},
        ]
        out += [{"kind": "vector", "group_id": gid, "item_id": "BO:" + c, "crit": c} for c in cu]
        out += [{"kind": "vector", "group_id": gid, "item_id": "OW:" + c, "crit": c} for c in cu]
        return out
    return [
        {"kind": "pairwise", "group_id": gid, "a": cu[i], "b": cu[j]}
        for i in range(len(cu))
        for j in range(i + 1, len(cu))
    ]


def group_item_count(group: dict) -> int:
    """이 그룹의 완전 응답에 필요한 항목 수(진행률 분모).

    pairwise: n(n-1)/2 쌍.
    bwm: Best·Worst 지목 2개 + Best-to-Others (n-1) + Others-to-Worst (n-1) = 2n.
    미지원 kind 는 pairwise 로 가정(진행률 분모라 죽지 않게 — build_results 방어 철학).
    """
    n = len(group["child_uuids"])
    kind = group.get("kind", "pairwise")
    if kind == "bwm":
        return 2 * n
    return n * (n - 1) // 2


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
