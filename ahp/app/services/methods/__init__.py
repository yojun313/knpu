"""가중치/랭킹 방법 플러그인 레지스트리 (PolyDecision 0단계).

`surveys.methods` 의 값(`"ahp"`, 향후 `"bwm"`/`"entropy"`/`"direct"`/`"topsis"`…)으로
플러그인을 찾는다. 0단계에는 AHP 하나만 등록돼 있고, 라우트/`build_results` 는 아직
직접 호출을 쓴다 — 플러그인 dispatch 전환은 다음 단계.
"""

from __future__ import annotations

from app.services.methods.ahp import AhpPlugin
from app.services.methods.base import Consistency, LocalResult, MethodPlugin

METHODS: dict[str, MethodPlugin] = {
    "ahp": AhpPlugin(),
}

DEFAULT_METHOD = "ahp"


def get_method(name: str | None) -> MethodPlugin:
    """미등록/누락 방법은 AHP로 폴백한다(기존 동작 = 전부 쌍대비교)."""
    return METHODS.get(name or DEFAULT_METHOD, METHODS[DEFAULT_METHOD])


# ── kind별 응답 body 검증 (put_answer가 dispatch 전환될 때 사용) ──────────
def _validate_pairwise(body: dict) -> dict:
    v = float(body["value"])
    if v <= 0:
        raise ValueError("비교값은 0보다 커야 합니다")
    return {"uuid_a": body["uuid_a"], "uuid_b": body["uuid_b"], "value": v}


KIND_VALIDATORS = {
    "pairwise": _validate_pairwise,
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
