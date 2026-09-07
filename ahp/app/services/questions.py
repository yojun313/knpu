"""질문 그룹 생성 — 계층(+대안 목록) + 방법 설정 → `surveys.groups[]`.

기존 `survey_service.generate_matrices` 를 일반화한다. "부모 하나당 그룹 하나"
구조와 순회 순서(= `active_section_index` 인덱스, CSV 열 순서의 근거)는 그대로
유지하고, 각 그룹의 실제 dict 는 그 노드에 배정된 **방법 플러그인**이 만든다.

`surveys.methods` shape (버전 bump 없이 `PUT /api/projects/{id}/survey` 로 편집):

    {
      "criteria":     {node_uuid: "ahp"|"bwm"|"entropy"|"direct", ...},  # 없으면 "ahp"
      "alternatives": "ahp"|"topsis"|"vikor"|"saw"|"edas"                 # 없으면 "ahp"
    }

0단계에는 AHP 플러그인만 등록돼 있어 결과는 기존 `generate_matrices` + 각 그룹에
`kind`("pairwise")·`scale` 두 키가 더 붙은 것과 동일하다.

변경 분류·응답 가지치기(`diff_groups`/`prune_answers`)는 아직 쌍대비교 전용이라
`survey_service` 구현을 그대로 재수출한다. 비-쌍대비교 kind 가 생기는 단계에서
kind별로 일반화한다.
"""

from __future__ import annotations

from app.services.methods import METHODS, get_method
from app.services.survey_service import (  # noqa: F401  (재수출 — 단일 import 지점)
    diff_has_impact,
    diff_matrices as diff_groups,
    prune_answers,
)


def normalize_methods(raw: dict | None) -> dict:
    """`surveys.methods` 정규화. 잘못된 모양은 조용히 기본값으로 되돌린다.

    `enabled` 는 "이 모델에서 활용할 분석"의 선언 목록(2.1) — 설계 페이지의
    상세설정 탭·방법 피커 선택지를 이 목록으로 제한한다. 없으면 실제 쓰임
    (criteria 값 + alternatives)에서 하위호환으로 도출한다.
    """
    raw = raw or {}
    known = set(METHODS)
    criteria = {}
    for k, v in (raw.get("criteria") or {}).items():
        if isinstance(k, str) and isinstance(v, str) and v:
            criteria[k] = v
    alternatives = raw.get("alternatives")
    if not isinstance(alternatives, str) or not alternatives:
        alternatives = "ahp"

    enabled_raw = raw.get("enabled")
    if isinstance(enabled_raw, list):
        enabled = [m for m in enabled_raw if isinstance(m, str) and m in known]
    else:
        enabled = []
    if not enabled:
        enabled = sorted((set(criteria.values()) | {alternatives}) & known)
    # 실제 배정된 방법은 항상 enabled 에 포함(선언과 사용의 정합성).
    for m in list(criteria.values()) + [alternatives]:
        if m in known and m not in enabled:
            enabled.append(m)
    if not enabled:
        enabled = ["ahp"]

    per_node = raw.get("criteria_per_node")
    if not isinstance(per_node, bool):
        per_node = len(set(criteria.values())) > 1  # 이미 혼합이면 고급 모드로 본다

    return {
        "criteria": criteria,
        "alternatives": alternatives,
        "enabled": enabled,
        "criteria_per_node": per_node,
    }


def generate_questions(
    nodes: list[dict],
    alternatives: list[dict] | None = None,
    methods: dict | None = None,
    settings: dict | None = None,
) -> list[dict]:
    methods = normalize_methods(methods)
    settings = settings or {}
    scale = settings.get("scale", 9)
    alt_layer_on = settings.get("alt_layer") == "on"
    criteria_methods = methods["criteria"]

    by_parent: dict[str, list[dict]] = {}
    for n in nodes:
        if n["parent_id"] is not None:
            by_parent.setdefault(n["parent_id"], []).append(n)
    by_id = {n["uuid"]: n for n in nodes}

    groups: list[dict] = []
    for parent_id, children in by_parent.items():
        children_sorted = sorted(children, key=lambda c: c["order"])
        method_name = criteria_methods.get(parent_id) or "ahp"
        g = get_method(method_name).generate_group(
            parent_uuid=parent_id,
            operand_uuids=[c["uuid"] for c in children_sorted],
            parent_name=by_id.get(parent_id, {}).get("name", ""),
            is_alternative=False,
            settings=settings,
        )
        g["method"] = method_name
        g["scale"] = scale
        groups.append(g)

    if alt_layer_on and alternatives:
        alt_ids = [a["uuid"] for a in sorted(alternatives, key=lambda a: a["order"])]
        leaves = [n for n in nodes if n["uuid"] not in by_parent]
        alt_method = methods["alternatives"] or "ahp"
        alt_plugin = get_method(alt_method)
        for leaf in leaves:
            g = alt_plugin.generate_group(
                parent_uuid=leaf["uuid"],
                operand_uuids=alt_ids,
                parent_name=leaf["name"],
                is_alternative=True,
                settings=settings,
            )
            g["method"] = alt_method
            g["scale"] = scale
            groups.append(g)

    return groups
