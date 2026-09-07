"""BWM 계산 코어 검사 — LP 가중치, 순서 일관성 OR, 입력기반 CR^I, 플러그인.

pytest 미도입 프로젝트라 plain 실행 스크립트.

    PYTHONPATH=/home/wcchoi/knpu:/home/wcchoi/knpu/ahp \
        /home/wcchoi/knpu/.venv/bin/python ahp/tests/check_methods_bwm.py
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

from app.services.mcdm.bwm_consistency import (  # noqa: E402
    cri_threshold,
    input_consistency,
    ordinal_consistency,
)
from app.services.mcdm.lp import bwm_linear_weights  # noqa: E402
from app.services.csv_schema import group_item_count, group_import_slots  # noqa: E402
from app.services.methods import KIND_VALIDATORS, METHODS, get_method  # noqa: E402
from app.services.methods.bwm import BwmPlugin  # noqa: E402
from app.services.questions import generate_questions  # noqa: E402
from app.services.result_service import build_results  # noqa: E402
from app.services.ahp_calc import to_stored_pair  # noqa: E402

P = BwmPlugin()


def approx(a, b, t=1e-6):
    return abs(a - b) <= t


def test_registry():
    assert get_method("bwm") is METHODS["bwm"]
    assert P.name == "bwm" and P.question_kinds() == ("bwm",)


def test_lp_perfectly_consistent():
    # C1=Best, C3=Worst. BO=(1,2,4), OW=(4,2,1). a_Bj·a_jW = 4 = a_BW ∀j → 완전 일관.
    crit = ["c1", "c2", "c3"]
    out = bwm_linear_weights(
        crit, "c1", "c3", {"c2": 2, "c3": 4}, {"c1": 4, "c2": 2}
    )
    w = out["weights"]
    assert approx(w["c1"], 4 / 7, 1e-4), w
    assert approx(w["c2"], 2 / 7, 1e-4)
    assert approx(w["c3"], 1 / 7, 1e-4)
    assert approx(sum(w.values()), 1.0)
    assert out["xi"] < 1e-6  # 완전 일관 → ξ_L ≈ 0


def test_input_consistency():
    crit = ["c1", "c2", "c3"]
    # 완전 일관 → CRI 0
    ic = input_consistency(crit, "c1", "c3", {"c2": 2, "c3": 4}, {"c1": 4, "c2": 2})
    assert approx(ic["CRI"], 0.0) and ic["passed"]
    assert approx(ic["threshold"], cri_threshold(4, 3))
    # 카디널 비일관: BO=(1,2,8), OW=(8,5,1). a_BW=8.
    #   CRI_c2 = |2·5 − 8| / (64 − 8) = 2/56
    ic2 = input_consistency(crit, "c1", "c3", {"c2": 2, "c3": 8}, {"c1": 8, "c2": 5})
    assert approx(ic2["CRI"], 2 / 56, 1e-4), ic2
    assert approx(ic2["CRI_by_criterion"]["c1"], 0.0)
    assert approx(ic2["CRI_by_criterion"]["c3"], 0.0)
    assert ic2["passed"]  # 2/56 ≈ .036 < threshold(8,3)=.1309


def test_ordinal_consistency():
    crit = ["c1", "c2", "c3", "c4"]
    # 완전 일관: aw[j] = a_BW / ab[j] (a_BW=6). bo 순위 == ow 순위 → OR 0.
    oc = ordinal_consistency(
        crit, "c1", "c4", {"c2": 2, "c3": 3, "c4": 6}, {"c1": 6, "c2": 3, "c3": 2}
    )
    assert approx(oc["OR"], 0.0), oc
    # ow가 c2/c3 순위를 뒤집음(bo: c2 더 중요, ow: c3 더 중요) → OR>0, c2·c3에서 잡힘
    bad = ordinal_consistency(
        crit, "c1", "c4", {"c2": 2, "c3": 3, "c4": 6}, {"c1": 6, "c2": 2, "c3": 4}
    )
    assert bad["OR"] > 0.0, bad
    assert bad["OR_by_criterion"]["c2"] > 0.0 and bad["OR_by_criterion"]["c3"] > 0.0
    assert approx(bad["OR_by_criterion"]["c1"], 0.0)


def test_plugin_derive_local():
    group = {"group_id": "g", "child_uuids": ["c1", "c2", "c3"]}
    resp = {"best": "c1", "worst": "c3", "BO:c2": 2, "BO:c3": 4, "OW:c1": 4, "OW:c2": 2}
    lr = P.derive_local(group, resp)
    assert lr.complete
    assert approx(lr.weights["c1"], 4 / 7, 1e-4)
    assert lr.ranking == ["c1", "c2", "c3"]
    assert lr.consistency.passed is True
    assert approx(lr.consistency.metrics["cri"], 0.0)
    assert approx(lr.consistency.metrics["or"], 0.0)
    assert lr.consistency.metrics["cro"] is not None
    # 불완전
    assert not P.derive_local(group, {"best": "c1", "worst": "c3"}).complete
    assert not P.derive_local(group, {}).complete


def test_plugin_aggregate_group():
    group = {"group_id": "g", "child_uuids": ["c1", "c2", "c3"]}
    rlist = [
        {"best": "c1", "worst": "c3", "BO:c2": 2, "BO:c3": 4, "OW:c1": 4, "OW:c2": 2},
        {"best": "c1", "worst": "c3", "BO:c2": 3, "BO:c3": 5, "OW:c1": 5, "OW:c2": 2},
        {"best": "c1", "worst": "c3"},  # 불완전 → skipped
    ]
    lr = P.aggregate_group(group, rlist, {})
    assert lr.complete and lr.skipped == [2]
    assert approx(sum(lr.weights.values()), 1.0)
    assert lr.ranking[0] == "c1"


def test_kind_validators_bwm():
    assert KIND_VALIDATORS["pick_best"]({"value": "u1"}) == ("best", "u1")
    assert KIND_VALIDATORS["pick_worst"]({"value": "u9"}) == ("worst", "u9")
    assert KIND_VALIDATORS["vector"]({"item_id": "BO:u2", "value": "3"}) == ("BO:u2", 3.0)
    for bad in (
        {"item_id": "XX:u2", "value": "3"},
        {"item_id": "BO:u2", "value": "0"},
        {"item_id": "OW:u2", "value": "10"},
    ):
        try:
            KIND_VALIDATORS["vector"](bad)
            raise AssertionError("should have raised")
        except ValueError:
            pass


def test_storage_path():
    # put_answer 가 하는 일을 흉내: KIND_VALIDATORS 로 (item_id, value) 뽑아
    # answers[group_id][item_id] 에 누적 → derive_local 완성 → 진행률 100%.
    _NODES = [
        {"uuid": "root", "parent_id": None, "name": "목표", "order": 0, "level": 0},
        {"uuid": "c1", "parent_id": "root", "name": "비용", "order": 0, "level": 1},
        {"uuid": "c2", "parent_id": "root", "name": "성능", "order": 1, "level": 1},
        {"uuid": "c3", "parent_id": "root", "name": "안전", "order": 2, "level": 1},
    ]
    group = generate_questions(
        _NODES, methods={"criteria": {"root": "bwm"}}, settings={}
    )[0]
    assert group["kind"] == "bwm" and group["method"] == "bwm"
    assert group_item_count(group) == 2 * 3  # 2n

    bodies = [
        {"group_id": "root", "kind": "pick_best", "value": "c1"},
        {"group_id": "root", "kind": "pick_worst", "value": "c3"},
        {"group_id": "root", "kind": "vector", "item_id": "BO:c2", "value": "2"},
        {"group_id": "root", "kind": "vector", "item_id": "BO:c3", "value": "4"},
        {"group_id": "root", "kind": "vector", "item_id": "OW:c1", "value": "4"},
        {"group_id": "root", "kind": "vector", "item_id": "OW:c2", "value": "2"},
    ]
    answers: dict = {}
    for b in bodies:
        iid, val = KIND_VALIDATORS[b["kind"]](b)
        answers.setdefault(b["group_id"], {})[iid] = val

    assert answers["root"] == {
        "best": "c1", "worst": "c3", "BO:c2": 2.0, "BO:c3": 4.0,
        "OW:c1": 4.0, "OW:c2": 2.0,
    }
    assert len(answers["root"]) == group_item_count(group)  # 진행률 100%

    lr = get_method(group["method"]).derive_local(group, answers["root"])
    assert lr.complete
    assert approx(lr.weights["c1"], 4 / 7, 1e-4)
    assert approx(lr.consistency.metrics["cri"], 0.0)


def test_pairwise_storage_unchanged():
    # pairwise 항목도 같은 (item_id, value) 계약을 지나며 방향 보정이 그대로 유지.
    iid, v = KIND_VALIDATORS["pairwise"](
        {"group_id": "g", "kind": "pairwise", "uuid_a": "z", "uuid_b": "a", "value": "3"}
    )
    assert iid == "a:z" and approx(v, 1 / 3)


def test_mixed_method_build_results():
    # root(AHP) → c1·c2·c3 ; c1(BWM) → c11·c12·c13. 혼합 방법 설문의 분석 파이프라인.
    nodes = [
        {"uuid": "root", "parent_id": None, "name": "목표", "order": 0, "level": 0},
        {"uuid": "c1", "parent_id": "root", "name": "비용", "order": 0, "level": 1},
        {"uuid": "c2", "parent_id": "root", "name": "성능", "order": 1, "level": 1},
        {"uuid": "c3", "parent_id": "root", "name": "안전", "order": 2, "level": 1},
        {"uuid": "c11", "parent_id": "c1", "name": "초기", "order": 0, "level": 2},
        {"uuid": "c12", "parent_id": "c1", "name": "운영", "order": 1, "level": 2},
        {"uuid": "c13", "parent_id": "c1", "name": "폐기", "order": 2, "level": 2},
    ]
    groups = generate_questions(
        nodes, methods={"criteria": {"c1": "bwm"}}, settings={}
    )
    by_id = {g["group_id"]: g for g in groups}
    assert by_id["root"]["kind"] == "pairwise" and by_id["c1"]["kind"] == "bwm"

    def PW(*t):
        d = {}
        for a, b, v in t:
            pid, sv = to_stored_pair(a, b, v)
            d[pid] = sv
        return d

    bwm_c1 = {"best": "c11", "worst": "c13", "BO:c12": 2, "BO:c13": 4, "OW:c11": 4, "OW:c12": 2}
    subs = {
        "r1": {"root": PW(("c1", "c2", 3), ("c1", "c3", 5), ("c2", "c3", 2)), "c1": dict(bwm_c1)},
        "r2": {"root": PW(("c1", "c2", 2), ("c1", "c3", 4), ("c2", "c3", 2)), "c1": dict(bwm_c1)},
    }
    res = build_results(nodes, groups, subs, {"aggregation": "AIP", "cr_threshold": 0.1})
    gw = res["global_weights"]
    # c1 하위(BWM)의 지역 가중치는 4/7·2/7·1/7 → 전역 = c1전역 × 그 값
    lw = res["local_weights"]["c1"]
    assert approx(lw["c11"], 4 / 7, 1e-3) and approx(lw["c13"], 1 / 7, 1e-3)
    assert approx(gw["c11"], gw["c1"] * lw["c11"], 1e-6)
    # 크래시 없이 per-respondent CR(= BWM은 CR^I) 이 채워짐
    assert res["per_respondent_cr"]["r1"].get("c1") is not None
    assert approx(sum(v for k, v in gw.items() if k in ("c11", "c12", "c13", "c2", "c3")), 1.0, 1e-6)

    # 결과 화면용 BWM 데이터 (1-6)
    assert res["group_kinds"]["c1"] == "bwm" and res["group_kinds"]["root"] == "pairwise"
    b = res["bwm"]["c1"]
    assert b["bw_distribution"]["best"] == {"c11": 2}  # r1·r2 모두 c11 을 Best 로
    assert b["bw_distribution"]["worst"] == {"c13": 2}
    pr = b["per_respondent"]["r1"]
    assert pr["cri"] is not None and pr["cri_threshold"] is not None and pr["or"] is not None
    assert approx(pr["cri"], 0.0)  # 완전 일관 응답


def test_import_slots_roundtrip():
    # 오프라인 반입 열 슬롯 → (파서가 만들) answers dict → BwmPlugin 이 읽는다.
    group = {"group_id": "g", "child_uuids": ["c1", "c2", "c3"]}
    group["kind"] = "bwm"
    slots = group_import_slots(group)
    assert [s["kind"] for s in slots] == [
        "pick_best", "pick_worst", "vector", "vector", "vector", "vector", "vector", "vector",
    ]
    assert len(slots) == 2 + 2 * 3  # 2 + 2n

    # 종이 양식 한 행을 파서가 채웠다고 치자 (Best=c1, Worst=c3)
    cells = ["c1", "c3", "1", "2", "4", "4", "2", "1"]  # best,worst, BO:c1..c3, OW:c1..c3
    ans = {}
    for s, cell in zip(slots, cells):
        if s["kind"] == "pick_best":
            ans["best"] = cell
        elif s["kind"] == "pick_worst":
            ans["worst"] = cell
        else:
            ans[s["item_id"]] = float(cell)
    lr = P.derive_local(group, ans)
    assert lr.complete
    assert approx(lr.weights["c1"], 4 / 7, 1e-4)
    # BO:c1(=Best 자신)·OW:c3(=Worst 자신) 잉여 칸은 무시돼도 결과 동일
    assert approx(lr.consistency.metrics["cri"], 0.0)

    # pairwise 그룹은 기존 쌍 슬롯 그대로
    pw = group_import_slots({"group_id": "p", "child_uuids": ["a", "b", "c"], "kind": "pairwise"})
    assert [s["kind"] for s in pw] == ["pairwise", "pairwise", "pairwise"]
    assert (pw[0]["a"], pw[0]["b"]) == ("a", "b")


def main() -> None:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    print(f"\n{len(tests)} checks passed.")


if __name__ == "__main__":
    main()
