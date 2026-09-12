"""AHP 방법 플러그인 — 쌍대비교 + 고유벡터 가중치 + CR.

기존 직접 호출(`ahp_calc.derive_weights`, `consistency.worst_offending_pairs`,
`aggregate.aggregate_aij/aip`)을 얇게 감싸기만 한다. 결과는 바이트 동일해야 한다
(0단계 합격 기준). 실제 수식은 `app/services/mcdm/` 공유 코어에서 당겨 쓴다.
"""

from __future__ import annotations

import math

from app.services.mcdm.aggregate import aggregate_aij, aggregate_aip, find_outliers
from app.services.mcdm.consistency import worst_offending_pairs
from app.services.mcdm.linalg import (
    IncompleteMatrixError,
    derive_weights,
    to_stored_pair,
)
from app.services.methods.base import Consistency, LocalResult


def _apply_overrides(pairs: dict, overrides: list[dict] | None) -> dict:
    """저장된 답(`{pair_id: value}`) 위에 what-if overrides를 얹는다.

    overrides 원소: `{uuid_a, uuid_b, value_a_over_b}` (respond_routes.group_eval와 동일).
    """
    merged = dict(pairs or {})
    for ov in overrides or []:
        try:
            pid, sv = to_stored_pair(
                ov["uuid_a"], ov["uuid_b"], float(ov["value_a_over_b"])
            )
        except (KeyError, TypeError, ValueError):
            continue
        merged[pid] = sv
    return merged


def _ranking(child_uuids: list[str], weights: dict[str, float]) -> list[str]:
    return sorted(child_uuids, key=lambda u: -weights.get(u, 0.0))


class AhpPlugin:
    name = "ahp"

    def question_kinds(self) -> tuple[str, ...]:
        return ("pairwise",)

    # ── ② 유도 ──────────────────────────────────────────────────────────
    def generate_group(
        self,
        *,
        parent_uuid: str,
        operand_uuids: list[str],
        parent_name: str,
        is_alternative: bool,
        settings: dict,
    ) -> dict:
        return {
            "group_id": f"alt:{parent_uuid}" if is_alternative else parent_uuid,
            "parent_uuid": parent_uuid,
            "child_uuids": list(operand_uuids),
            "kind": "pairwise",
            "question_text": (
                f"'{parent_name}' 기준에서 다음 대안들이 서로 얼마나 우수한지 "
                f"비교해 주세요."
                if is_alternative
                else f"'{parent_name}' 측면에서 다음 항목들이 서로 얼마나 중요한지 "
                f"비교해 주세요."
            ),
            "is_alternative": is_alternative,
        }

    # ── ④ 검증 ──────────────────────────────────────────────────────────
    def _consistency(
        self, child_uuids: list[str], pairs: dict, cr: float | None, cr_threshold: float
    ) -> Consistency:
        if cr is None:  # 항목 3개 미만 — 비일관성이 정의되지 않음
            return Consistency(passed=None, metrics={}, threshold=None)
        worst = worst_offending_pairs(child_uuids, pairs, top_k=3)
        return Consistency(
            passed=cr <= cr_threshold,  # 안내용 — 제출을 막지 않는다
            metrics={"cr": cr},
            threshold=cr_threshold,
            locus=[w.pair_id for w in worst],
            detail=[w.to_dict() for w in worst],
        )

    def validate(
        self,
        group: dict,
        responses: dict,
        *,
        cr_threshold: float = 0.1,
        overrides: list[dict] | None = None,
        settings: dict | None = None,
    ) -> Consistency | None:
        return self.derive_local(
            group, responses, overrides=overrides, cr_threshold=cr_threshold
        ).consistency

    # ── ⑤ 계산 (개인) ──────────────────────────────────────────────────
    def derive_local(
        self,
        group: dict,
        responses: dict,
        *,
        overrides: list[dict] | None = None,
        cr_threshold: float = 0.1,
        settings: dict | None = None,  # noqa: ARG002  (BWM만 사용 — 시그니처 통일)
    ) -> LocalResult:
        child_uuids = list(group["child_uuids"])
        pairs = _apply_overrides(responses, overrides)
        try:
            wr = derive_weights(child_uuids, pairs)
        except IncompleteMatrixError:
            return LocalResult(weights={}, ranking=[], complete=False, consistency=None)
        return LocalResult(
            weights=wr.weights,
            ranking=_ranking(child_uuids, wr.weights),
            complete=True,
            consistency=self._consistency(child_uuids, pairs, wr.cr, cr_threshold),
        )

    # ── ⑤ 계산 (그룹) ──────────────────────────────────────────────────
    def aggregate_group(
        self,
        group: dict,
        responses_by_respondent: list[dict],
        settings: dict,
    ) -> LocalResult:
        child_uuids = list(group["child_uuids"])

        if len(child_uuids) == 1:
            return LocalResult(
                weights={child_uuids[0]: 1.0},
                ranking=list(child_uuids),
                complete=True,
            )

        non_empty = [r for r in responses_by_respondent if r]
        if not non_empty:
            return LocalResult(
                weights={u: 0.0 for u in child_uuids},
                ranking=list(child_uuids),
                complete=False,
            )

        aggregation = settings.get("aggregation", "AIP")
        skipped: list = []
        try:
            if aggregation == "AIJ":
                wr, _merged = aggregate_aij(child_uuids, non_empty)
                group_w, avg_cr = wr.weights, wr.cr
            else:
                group_w, per, skipped = aggregate_aip(child_uuids, non_empty)
                crs = [r.cr for r in per if r.cr is not None]
                avg_cr = sum(crs) / len(crs) if crs else None
        except (ValueError, IncompleteMatrixError):
            return LocalResult(
                weights={u: 0.0 for u in child_uuids},
                ranking=list(child_uuids),
                complete=False,
            )

        return LocalResult(
            weights=group_w,
            ranking=_ranking(child_uuids, group_w),
            complete=True,
            consistency=Consistency(
                passed=None,
                metrics={"avg_cr": avg_cr} if avg_cr is not None else {},
                threshold=None,
            ),
            skipped=skipped,
        )

    # ── 표시 계층 보조 ─────────────────────────────────────────────────
    def merge_responses(self, group: dict, responses: list[dict]) -> dict:
        acc: dict[str, list[float]] = {}
        for r in responses or []:
            for pid, v in (r or {}).items():
                try:
                    fv = float(v)
                except (TypeError, ValueError):
                    continue
                if fv > 0:
                    acc.setdefault(pid, []).append(fv)
        return {
            pid: math.exp(sum(math.log(v) for v in vs) / len(vs))
            for pid, vs in acc.items()
            if vs
        }

    def response_outliers(
        self, group: dict, responses_by_rid: dict[str, dict]
    ) -> list[dict]:
        by_item: dict[str, dict[str, float]] = {}
        for rid, ans in (responses_by_rid or {}).items():
            for pid, v in (ans or {}).items():
                try:
                    fv = float(v)
                except (TypeError, ValueError):
                    continue
                by_item.setdefault(pid, {})[rid] = fv
        out: list[dict] = []
        for pid, vals_by_rid in by_item.items():
            if len(vals_by_rid) < 4:
                continue
            rids = list(vals_by_rid.keys())
            indexed = {i: vals_by_rid[rids[i]] for i in range(len(rids))}
            bad = find_outliers(indexed)
            if bad:
                out.append(
                    {
                        "item_id": pid,
                        "outlier_respondents": [rids[i] for i in bad],
                    }
                )
        return out


PLUGIN = AhpPlugin()
