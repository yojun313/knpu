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
from app.services.methods import KIND_VALIDATORS, METHODS, get_method  # noqa: E402
from app.services.methods.bwm import BwmPlugin  # noqa: E402

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


def main() -> None:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    print(f"\n{len(tests)} checks passed.")


if __name__ == "__main__":
    main()
