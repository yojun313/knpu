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
from app.services.consistency import worst_offending_pairs  # noqa: E402
from app.services.methods import KIND_VALIDATORS, METHODS, get_method  # noqa: E402
from app.services.methods.ahp import AhpPlugin  # noqa: E402
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
