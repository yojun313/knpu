"""그룹 집계·합의도 프리미티브.

0단계: `app.services.aggregate` 재수출. 기하평균 통합(비율척도 정합)·변동계수·
Kendall W·MAD 이상치는 방법 무관하게 공유한다.
"""

from __future__ import annotations

from app.services.aggregate import (  # noqa: F401  (재수출)
    aggregate_aij,
    aggregate_aip,
    coefficient_of_variation,
    find_outliers,
    geometric_mean,
    kendalls_w,
)

__all__ = [
    "aggregate_aij",
    "aggregate_aip",
    "coefficient_of_variation",
    "find_outliers",
    "geometric_mean",
    "kendalls_w",
]
