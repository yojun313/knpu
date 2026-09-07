"""가중치/랭킹 방법 플러그인 레지스트리 (PolyDecision 0단계).

`surveys.methods` 의 값(`"ahp"`, 향후 `"bwm"`/`"entropy"`/`"direct"`/`"topsis"`…)으로
플러그인을 찾는다. 0단계에는 AHP 하나만 등록돼 있고, 라우트/`build_results` 는 아직
직접 호출을 쓴다 — 플러그인 dispatch 전환은 다음 단계.
"""

from __future__ import annotations

from app.services.methods.ahp import AhpPlugin
from app.services.methods.base import Consistency, LocalResult, MethodPlugin
from app.services.methods.bwm import BwmPlugin

METHODS: dict[str, MethodPlugin] = {
    "ahp": AhpPlugin(),
    "bwm": BwmPlugin(),
}

DEFAULT_METHOD = "ahp"


def get_method(name: str | None) -> MethodPlugin:
    """미등록/누락 방법은 AHP로 폴백한다(기존 동작 = 전부 쌍대비교)."""
    return METHODS.get(name or DEFAULT_METHOD, METHODS[DEFAULT_METHOD])


# ── kind별 응답 body → (item_id, value) 정규화 ─────────────────────────────
# put_answer 가 `answers[group_id][item_id] = value` 로 저장할 때 쓴다.
# 클라이언트가 보내는 kind 는 항목 수준(pairwise / pick_best / pick_worst / vector).
from app.services.ahp_calc import to_stored_pair  # noqa: E402


def _v_pairwise(body: dict):
    v = float(body["value"])
    if v <= 0:
        raise ValueError("비교값은 0보다 커야 합니다")
    return to_stored_pair(body["uuid_a"], body["uuid_b"], v)  # (pair_id, 저장값)


def _v_pick_best(body: dict):
    return "best", str(body["value"])


def _v_pick_worst(body: dict):
    return "worst", str(body["value"])


def _v_vector(body: dict):
    iid = str(body["item_id"])
    if not (iid.startswith("BO:") or iid.startswith("OW:")):
        raise ValueError(f"vector item_id 형식 오류: {iid}")
    v = float(body["value"])
    if not (1 <= v <= 9):
        raise ValueError("BWM 비교값은 1~9 범위여야 합니다")
    return iid, v


KIND_VALIDATORS = {
    "pairwise": _v_pairwise,
    "pick_best": _v_pick_best,
    "pick_worst": _v_pick_worst,
    "vector": _v_vector,
}

__all__ = [
    "METHODS",
    "DEFAULT_METHOD",
    "get_method",
    "KIND_VALIDATORS",
    "MethodPlugin",
    "Consistency",
    "LocalResult",
]
