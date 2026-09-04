"""AhpPlugin 패리티 검사 — 플러그인 결과가 기존 직접 호출과 바이트 동일한지.

pytest 미도입 프로젝트라 plain 실행 스크립트다. 실패 시 AssertionError로 죽는다.

    PYTHONPATH=/home/wcchoi/knpu:/home/wcchoi/knpu/ahp \
        /home/wcchoi/knpu/.venv/bin/python ahp/tests/check_methods_ahp.py
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_AHP_DIR = os.path.dirname(_HERE)
_REPO_ROOT = os.path.dirname(_AHP_DIR)
for _p in (_REPO_ROOT, _AHP_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.services.ahp_calc import derive_weights, to_stored_pair  # noqa: E402
from app.services.aggregate import aggregate_aij, aggregate_aip  # noqa: E402
from app.services.consistency import worst_offending_pairs  # noqa: E402
from app.routes.collection_routes import respondent_progress_summary  # noqa: E402
from app.routes.entry_routes import _compute_cr_for_matrix  # noqa: E402
from app.services.methods import KIND_VALIDATORS, METHODS, get_method  # noqa: E402
from app.services.methods.ahp import AhpPlugin  # noqa: E402
from app.services.questions import generate_questions, normalize_methods  # noqa: E402
from app.services.result_service import build_results  # noqa: E402
from app.services.survey_service import generate_matrices  # noqa: E402

P = AhpPlugin()


def approx(a: float, b: float, t: float = 1e-9) -> bool:
    return abs(a - b) <= t


def _pairs(*triples) -> dict:
    d: dict = {}
    for a, b, v in triples:
        pid, sv = to_stored_pair(a, b, v)
        d[pid] = sv
    return d


def test_registry():
    assert get_method("ahp") is METHODS["ahp"]
    assert get_method(None).name == "ahp"
    assert get_method("bwm").name == "ahp"  # 미등록 → AHP 폴백
    assert P.question_kinds() == ("pairwise",)


def test_derive_local_n3():
    cu = ["c1", "c2", "c3"]
    pairs = _pairs(("c1", "c2", 3.0), ("c1", "c3", 5.0), ("c2", "c3", 2.0))
    g = {"group_id": "root", "child_uuids": cu}
    lr = P.derive_local(g, pairs, cr_threshold=0.1)
    wr = derive_weights(cu, pairs)
    assert lr.complete
    for u in cu:
        assert approx(lr.weights[u], wr.weights[u])
    assert lr.ranking == sorted(cu, key=lambda u: -wr.weights[u])
    assert approx(lr.consistency.metrics["cr"], wr.cr)
    assert lr.consistency.passed == (wr.cr <= 0.1)
    worst = worst_offending_pairs(cu, pairs, top_k=3)
    assert lr.consistency.locus == [w.pair_id for w in worst]
    assert lr.consistency.detail == [w.to_dict() for w in worst]


def test_derive_local_edge():
    # n=2 → CR 미정의
    p2 = _pairs(("a", "b", 4.0))
    lr2 = P.derive_local({"group_id": "x", "child_uuids": ["a", "b"]}, p2)
    assert lr2.complete and lr2.consistency.passed is None and lr2.consistency.metrics == {}
    # n=1
    lr1 = P.derive_local({"group_id": "y", "child_uuids": ["only"]}, {})
    assert lr1.complete and lr1.weights == {"only": 1.0} and lr1.consistency.passed is None
    # 불완전
    cu = ["c1", "c2", "c3"]
    part = _pairs(("c1", "c2", 3.0))
    lri = P.derive_local({"group_id": "z", "child_uuids": cu}, part)
    assert not lri.complete and lri.weights == {} and lri.consistency is None


def test_overrides():
    cu = ["c1", "c2", "c3"]
    pairs = _pairs(("c1", "c2", 3.0), ("c1", "c3", 5.0), ("c2", "c3", 2.0))
    g = {"group_id": "root", "child_uuids": cu}
    ov = [{"uuid_a": "c1", "uuid_b": "c2", "value_a_over_b": 1.0}]
    lro = P.derive_local(g, pairs, overrides=ov)
    manual = dict(pairs)
    pid, sv = to_stored_pair("c1", "c2", 1.0)
    manual[pid] = sv
    wro = derive_weights(cu, manual)
    for u in cu:
        assert approx(lro.weights[u], wro.weights[u])
    assert approx(lro.consistency.metrics["cr"], wro.cr)


_NODES = [
    {"uuid": "root", "parent_id": None, "name": "목표", "order": 0, "level": 0},
    {"uuid": "c1", "parent_id": "root", "name": "비용", "order": 0, "level": 1},
    {"uuid": "c2", "parent_id": "root", "name": "성능", "order": 1, "level": 1},
    {"uuid": "c3", "parent_id": "root", "name": "안전", "order": 2, "level": 1},
]


def test_aggregate_group_parity():
    groups = generate_matrices(_NODES)
    subs = {
        "r1": {"root": _pairs(("c1", "c2", 3), ("c1", "c3", 5), ("c2", "c3", 2))},
        "r2": {"root": _pairs(("c1", "c2", 2), ("c1", "c3", 4), ("c2", "c3", 2))},
        "r3": {"root": _pairs(("c1", "c2", 4), ("c1", "c3", 6), ("c2", "c3", 2))},
    }
    resp_list = [s["root"] for s in subs.values()]
    for agg in ("AIP", "AIJ"):
        settings = {"aggregation": agg, "cr_threshold": 0.1}
        lrg = P.aggregate_group(groups[0], resp_list, settings)
        br = build_results(_NODES, groups, subs, settings)
        for u in ("c1", "c2", "c3"):
            assert approx(lrg.weights[u], br["local_weights"]["root"][u])
        assert lrg.complete


def test_generate_group_shape():
    gg = P.generate_group(
        parent_uuid="root",
        operand_uuids=["c1", "c2", "c3"],
        parent_name="목표",
        is_alternative=False,
        settings={},
    )
    gm = [m for m in generate_matrices(_NODES) if m["group_id"] == "root"][0]
    assert gg["group_id"] == gm["group_id"]
    assert gg["child_uuids"] == gm["child_uuids"]
    assert gg["question_text"] == gm["question_text"]
    assert gg["is_alternative"] is False
    assert gg["kind"] == "pairwise"


def test_generate_questions_parity():
    # 대안 계층까지 켜서 순회 순서·question_text 가 generate_matrices 와 동일한지,
    # 각 그룹에 kind="pairwise" · scale 이 붙는지.
    nodes = _NODES + [
        {"uuid": "c11", "parent_id": "c1", "name": "초기", "order": 0, "level": 2},
        {"uuid": "c12", "parent_id": "c1", "name": "운영", "order": 1, "level": 2},
    ]
    alts = [
        {"uuid": "A", "name": "안A", "order": 0},
        {"uuid": "B", "name": "안B", "order": 1},
    ]
    settings = {"alt_layer": "on", "scale": 5}
    legacy = generate_matrices(nodes, alts, alt_layer_on=True)
    new = generate_questions(nodes, alts, methods={}, settings=settings)
    assert [g["group_id"] for g in new] == [g["group_id"] for g in legacy]
    for gn, gl in zip(new, legacy):
        assert gn["child_uuids"] == gl["child_uuids"]
        assert gn["question_text"] == gl["question_text"]
        assert gn["is_alternative"] == gl["is_alternative"]
        assert gn["parent_uuid"] == gl["parent_uuid"]
        assert gn["kind"] == "pairwise"
        assert gn["method"] == "ahp"
        assert gn["scale"] == 5
    # 미등록 방법은 조용히 AHP 폴백 (그룹이 그대로 생성됨)
    m = normalize_methods({"criteria": {"root": "bwm"}, "alternatives": "topsis"})
    assert m == {"criteria": {"root": "bwm"}, "alternatives": "topsis"}
    fb = generate_questions(nodes, alts, methods=m, settings=settings)
    assert [g["group_id"] for g in fb] == [g["group_id"] for g in legacy]
    assert all(g["kind"] == "pairwise" for g in fb)


def test_route_helpers_parity():
    # 4단계에서 플러그인 dispatch로 바꾼 라우트 헬퍼가 기존 직접 호출과 동일한지.
    groups = generate_questions(_NODES, methods={}, settings={"scale": 9})
    root = [g for g in groups if g["group_id"] == "root"][0]
    full = _pairs(("c1", "c2", 3.0), ("c1", "c3", 5.0), ("c2", "c3", 2.0))
    part = _pairs(("c1", "c2", 3.0))

    # entry_routes._compute_cr_for_matrix
    ci = _compute_cr_for_matrix(root, {"root": full})
    wr = derive_weights(root["child_uuids"], full)
    assert ci["complete"] and approx(ci["cr"], wr.cr)
    assert ci["weights"] == wr.weights
    assert _compute_cr_for_matrix(root, {"root": part})["complete"] is False

    # collection_routes.respondent_progress_summary — worst_cr = max 완성된 그룹 CR
    ans = {"root": full}
    s = respondent_progress_summary(groups, ans)
    assert approx(s["worst_cr"], wr.cr)
    s2 = respondent_progress_summary(groups, {"root": part})
    assert s2["worst_cr"] is None and s2["complete"] is False

    # reveal_group 식 avg_cr: aggregate_group.consistency.avg_cr == 기존 계산
    rp = [full, _pairs(("c1", "c2", 2.0), ("c1", "c3", 4.0), ("c2", "c3", 2.0))]
    for agg in ("AIP", "AIJ"):
        lr = P.aggregate_group(root, rp, {"aggregation": agg})
        if agg == "AIJ":
            wexp, _m = aggregate_aij(root["child_uuids"], rp)
            exp = wexp.cr
        else:
            _gw, per, _sk = aggregate_aip(root["child_uuids"], rp)
            crs = [r.cr for r in per if r.cr is not None]
            exp = sum(crs) / len(crs) if crs else None
        got = lr.consistency.metrics.get("avg_cr")
        assert (got is None and exp is None) or approx(got, exp), (agg, got, exp)


def test_kind_validators():
    assert KIND_VALIDATORS["pairwise"](
        {"uuid_a": "a", "uuid_b": "b", "value": "3"}
    ) == {"uuid_a": "a", "uuid_b": "b", "value": 3.0}
    for bad in ({"uuid_a": "a", "uuid_b": "b", "value": "0"},):
        try:
            KIND_VALIDATORS["pairwise"](bad)
            raise AssertionError("should have raised")
        except ValueError:
            pass


def main() -> None:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    print(f"\n{len(tests)} checks passed.")


if __name__ == "__main__":
    main()
