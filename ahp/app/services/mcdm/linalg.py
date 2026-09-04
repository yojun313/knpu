"""선형대수·쌍대비교 프리미티브.

0단계: `app.services.ahp_calc` 재수출. AHP가 쓰고, 향후 다른 비율척도 방법도
쌍대비교 저장 규약(`pair_id` = 사전순 `"lo:hi"`, 값 = lo/hi 중요도)을 공유한다.
"""

from __future__ import annotations

from app.services.ahp_calc import (  # noqa: F401  (재수출)
    IncompleteMatrixError,
    RI_TABLE,
    WeightResult,
    build_matrix,
    derive_weights,
    eigen_weights,
    geomean_weights,
    pair_id,
    to_stored_pair,
)

__all__ = [
    "IncompleteMatrixError",
    "RI_TABLE",
    "WeightResult",
    "build_matrix",
    "derive_weights",
    "eigen_weights",
    "geomean_weights",
    "pair_id",
    "to_stored_pair",
]
