"""일관성 진단 프리미티브.

0단계: `app.services.consistency` 재수출. `worst_offending_pairs`(편차 상위 쌍
지목)와 `nearest_saaty_label`(소수 → 응답형 라벨 스냅)은 AHP·BWM이 공유한다.

방법별 임계값 표(BWM `CR^I`/`CR^O` (n, scale) 표 등)와 통합 진입점
`evaluate(method, group, responses)` 는 BWM을 붙이는 단계에서 이 모듈에 추가한다
(설계: `~/.claude/plans/ahp-compiled-shore.md` §6-B). 그때까지 방법별 판정은 각
플러그인의 `validate()` 안에 둔다.
"""

from __future__ import annotations

from app.services.consistency import (  # noqa: F401  (재수출)
    WorstPair,
    nearest_saaty_label,
    worst_offending_pairs,
)

__all__ = ["WorstPair", "nearest_saaty_label", "worst_offending_pairs"]
