"""가중치/랭킹 방법 플러그인의 공통 계약 (PolyDecision 0단계).

한 "질문 그룹"(기존 AHP 비교행렬의 일반화 — `surveys.groups[]` 원소)에 대해
방법 하나가 다음을 담당한다:

  ② 유도  : `generate_group()`   — 계층 노드에서 이 방법의 질문 그룹을 만든다
  ④ 검증  : `validate()`         — 일관성 지표·문제 문항(locus)을 낸다 (안내용, 게이트 아님)
  ⑤ 계산  : `derive_local()`     — 개인 응답 → 국소 가중치·순위
            `aggregate_group()`  — 응답자들 → 그룹 국소 가중치·순위

플러그인은 얇게 유지하고 실제 수식은 `app/services/mcdm/` 공유 코어를 호출한다
(설계: `~/.claude/plans/ahp-compiled-shore.md` §6-B).

`responses` 는 그 그룹의 답만 담은 `{item_id: value}` dict다:
  - pairwise : `{pair_id: float}`  (pair_id = 사전순 `"lo:hi"`)
  - bwm      : `{"best": code, "worst": code, "BO:<uuid>": n, "OW:<uuid>": n, ...}` (예정)
  - vector   : `{operand_uuid: 0..100}` (예정)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class Consistency:
    """④ 검증 결과.

    `passed` 는 **안내용**이다 — AHP CR과 동일하게 "높으면 재고 권고"만 하고
    제출을 막는 데 쓰지 않는다(설계 결정 5). `None` 은 판정 불가/불필요
    (예: 항목 3개 미만이라 비일관성이 정의되지 않음).
    """

    passed: bool | None
    metrics: dict[str, float]              # AHP: {"cr": v} / BWM: {"or":, "cri":, "cro":}
    threshold: float | None
    locus: list[str] = field(default_factory=list)   # 문제 item_id (재응답 유도)
    detail: list[dict] = field(default_factory=list)  # worst pair 등 표시용 상세

    @property
    def value(self) -> float | None:
        """방법 무관 대표 비일관성 값 — AHP CR 또는 BWM CR^I. 화면·payload용."""
        return self.metrics.get("cr", self.metrics.get("cri"))


@dataclass
class LocalResult:
    """한 질문 그룹의 국소 결과."""

    weights: dict[str, float]              # operand_id -> 정규화 국소 가중치 (합=1)
    ranking: list[str]                     # 가중치 내림차순 operand_id
    complete: bool                         # 계산 가능할 만큼 응답이 채워졌는가
    consistency: Consistency | None = None
    skipped: list = field(default_factory=list)  # 집계에서 제외된 응답자 인덱스 등


@runtime_checkable
class MethodPlugin(Protocol):
    name: str

    def question_kinds(self) -> tuple[str, ...]:
        """이 방법이 만드는 문항 종류 (예: ("pairwise",))."""
        ...

    def generate_group(
        self,
        *,
        parent_uuid: str,
        operand_uuids: list[str],
        parent_name: str,
        is_alternative: bool,
        settings: dict,
    ) -> dict:
        """`surveys.groups[]` 원소 dict를 만든다:
        `{group_id, parent_uuid, child_uuids, kind, question_text, is_alternative}`.
        """
        ...

    def validate(
        self,
        group: dict,
        responses: dict,
        *,
        cr_threshold: float = 0.1,
        overrides: list[dict] | None = None,
    ) -> Consistency | None:
        ...

    def derive_local(
        self,
        group: dict,
        responses: dict,
        *,
        overrides: list[dict] | None = None,
        cr_threshold: float = 0.1,
    ) -> LocalResult:
        ...

    def aggregate_group(
        self,
        group: dict,
        responses_by_respondent: list[dict],
        settings: dict,
    ) -> LocalResult:
        ...
