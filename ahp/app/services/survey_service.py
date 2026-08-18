"""설문지 문항(matrices) 자동 생성 + 계층 변경 시 버전 분류·응답 가지치기.

설문지의 matrices는 계층의 "부모 하나당 비교행렬 하나"로 기계적으로 뽑힌다.
계층이 나중에 바뀌면(형제 추가/삭제/이동) 이미 받은 응답 중 무엇이 살아남는지를
PLAN.md 7.4의 규칙대로 정확히 갈라야 한다 — 대충 버전만 올리고 응답을 통째로
버리거나, 반대로 안 맞는 크기의 행렬을 그대로 쓰다가 계산이 터지면 안 된다.

DB 접근이 없는 순수 함수 계층이라 단위 테스트 대상이다.
"""

from __future__ import annotations


def generate_matrices(
    nodes: list[dict],
    alternatives: list[dict] | None = None,
    alt_layer_on: bool = False,
) -> list[dict]:
    """계층 노드에서 '부모 하나당 비교행렬 하나'를 기계적으로 뽑는다.

    자식이 없는 리프는 비교할 게 없으니 건너뛴다. 자식이 1개뿐인 부모도 행렬을
    만들어 둔다 — ahp_calc.derive_weights()가 n=1을 가중치 1.0으로 자동 처리하므로
    "경쟁자가 없으니 전부 가져간다"는 뜻을 계산 계층에서 그대로 살릴 수 있고,
    나중에 형제가 추가돼도(children_changed) 행렬이 이미 존재해 매끄럽게 이어진다.
    matrix_id는 parent_uuid를 그대로 쓴다 — 부모 하나에 행렬 하나가 항상 1:1이라
    별도 식별자를 만들 이유가 없고, ahp_calc.global_weights()의 matrix_of_parent
    매핑도 항등함수가 되어 계산 계층이 더 단순해진다.

    alt_layer_on이면 최하위(leaf) 기준마다 "대안들 간 비교" 행렬을 하나씩 추가로
    만든다(matrix_id = "alt:<leaf_uuid>", is_alternative=True로 표시해서 결과
    화면이 기준 비교와 구분해 대안 최종 점수를 합성할 수 있게 한다). 대안 자체는
    계층이 아니라 평탄한 목록이라, leaf 하나당 같은 대안 목록을 그대로 재사용한다.
    """
    by_parent: dict[str, list[dict]] = {}
    for n in nodes:
        if n["parent_id"] is not None:
            by_parent.setdefault(n["parent_id"], []).append(n)

    by_id = {n["uuid"]: n for n in nodes}
    matrices = []
    for parent_id, children in by_parent.items():
        children_sorted = sorted(children, key=lambda c: c["order"])
        parent_name = by_id.get(parent_id, {}).get("name", "")
        matrices.append(
            {
                "matrix_id": parent_id,
                "parent_uuid": parent_id,
                "child_uuids": [c["uuid"] for c in children_sorted],
                "question_text": (
                    f"'{parent_name}' 측면에서 다음 항목들이 서로 얼마나 중요한지 "
                    f"비교해 주세요."
                ),
                "is_alternative": False,
            }
        )

    if alt_layer_on and alternatives:
        alt_ids = [a["uuid"] for a in sorted(alternatives, key=lambda a: a["order"])]
        leaves = [n for n in nodes if n["uuid"] not in by_parent]
        for leaf in leaves:
            matrices.append(
                {
                    "matrix_id": f"alt:{leaf['uuid']}",
                    "parent_uuid": leaf["uuid"],
                    "child_uuids": alt_ids,
                    "question_text": (
                        f"'{leaf['name']}' 기준에서 다음 대안들이 서로 얼마나 "
                        f"우수한지 비교해 주세요."
                    ),
                    "is_alternative": True,
                }
            )

    return matrices


def diff_matrices(old_matrices: list[dict], new_matrices: list[dict]) -> dict:
    """이전/새 matrices를 비교해 matrix_id별 변경 내역을 만든다.

    반환값의 added_children/removed_children은 이미 받은 응답 중 무엇을 버리고
    무엇을 살릴지 그대로 실행 가능한 형태다 — prune_answers()가 이 결과를 받아
    실제로 응답 문서를 정리한다.
    """
    old_by_id = {m["matrix_id"]: m for m in old_matrices}
    new_by_id = {m["matrix_id"]: m for m in new_matrices}

    diff = {
        "removed_matrix_ids": sorted(set(old_by_id) - set(new_by_id)),
        "changes": {},
    }

    for mid, new_m in new_by_id.items():
        old_m = old_by_id.get(mid)
        new_children = set(new_m["child_uuids"])

        if old_m is None:
            diff["changes"][mid] = {
                "status": "new",
                "added_children": sorted(new_children),
                "removed_children": [],
                "kept_children": [],
            }
            continue

        old_children = set(old_m["child_uuids"])
        if old_children == new_children:
            diff["changes"][mid] = {
                "status": "unchanged",
                "added_children": [],
                "removed_children": [],
                "kept_children": sorted(new_children),
            }
            continue

        diff["changes"][mid] = {
            "status": "children_changed",
            "added_children": sorted(new_children - old_children),
            "removed_children": sorted(old_children - new_children),
            "kept_children": sorted(old_children & new_children),
        }

    return diff


def diff_has_impact(diff: dict) -> bool:
    """응답에 실제로 영향을 주는 변경이 하나라도 있는지(문구만 바뀐 건 영향 없음)."""
    if diff["removed_matrix_ids"]:
        return True
    return any(c["status"] == "children_changed" for c in diff["changes"].values())


def prune_answers(answers: dict, diff: dict) -> tuple[dict, bool]:
    """응답 문서 하나(answers: {matrix_id: {pair_id: value}})에 diff를 적용해
    무효화된 항목만 제거한다. (정리된 answers, 뭔가 바뀌었는지)를 돌려준다.

    호출부가 이 함수를 쓰기 전에 원본을 이미 어딘가(변경 이력)에 보존해 뒀다는
    전제다 — 폐기된 응답도 삭제하지 않고 보존한다는 PLAN.md 4.4 원칙은 여기가
    아니라 호출부(survey_routes.resync)의 책임이다.
    """
    changed = False
    result: dict = {}
    for mid, pairs in answers.items():
        if mid in diff["removed_matrix_ids"]:
            changed = True
            continue

        change = diff["changes"].get(mid)
        if not change or change["status"] == "unchanged":
            result[mid] = pairs
            continue

        removed = set(change["removed_children"])
        if not removed:
            result[mid] = pairs
            continue

        kept_pairs = {}
        for pid, v in pairs.items():
            a, b = pid.split(":", 1)
            if a in removed or b in removed:
                changed = True
                continue
            kept_pairs[pid] = v
        result[mid] = kept_pairs

    return result, changed
