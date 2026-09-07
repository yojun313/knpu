# PolyDecision 방법론 고도화 로드맵

> 이 문서는 **구현 계획이 아니라 설계 합의용 초안**이다. 각 항목은 승인 후
> 별도 Phase 로 착수한다. 우선순위·난이도·의존성은 §6 표 참조.

---

## 1. 현재 구조 (확장의 전제)

계산·현출이 방법별로 플러그인화돼 있어, **새 방법 = 백엔드 플러그인 1개 +
프런트 뷰 객체 1개** 등록으로 끝난다.

| 층 | 위치 | 계약 |
|---|---|---|
| 계산 코어 | `app/services/mcdm/` (`linalg` 고유벡터·기하평균, `lp` 선형계획, `bwm_consistency`, `aggregate`, `consistency`) | 순수 수식. 방법 무관 프리미티브 |
| 방법 플러그인 | `app/services/methods/{ahp,bwm}.py` (`MethodPlugin` 프로토콜, `base.py`) | `generate_group` / `validate` / `derive_local` / `aggregate_group` / `merge_responses` / `response_outliers` |
| 레지스트리 | `methods/__init__.py` `METHODS`, `KIND_VALIDATORS` | `get_method(name)` — 미등록은 AHP 폴백 |
| 저장 규약 | `surveys.methods = {enabled[], criteria{node:method}, alternatives, criteria_per_node}` · `responses.answers[group_id] = {item_id: value}` | 방법이 answer shape 정의 |
| 프런트 뷰 | `static/js/method_views.js` `window.MCDMViews[kind]` | `consoleColumns` / `consoleCells` / `consoleSave` / `worstHtml` / `revealRows` |
| 응답 렌더러 | `static/js/respond.js` `RENDERERS[kind]` | `renderBody` / `isComplete` / `overrides` |

**새 방법 추가 시 건드리는 곳(고정 목록):** `mcdm/`에 수식 → `methods/<x>.py` →
`METHODS`·`KIND_VALIDATORS` 등록 → `csv_schema.py`(오프라인 슬롯) →
`method_views.js`·`respond.js` 뷰 → `survey_editor`/`designer`의 방법 라벨.
`result_service.build_results`·`collection_routes`는 이미 `get_method()` 경유라
분기 없이 동작한다.

---

## 2. AHP 트랙

### 2-A. 불완전 쌍대비교 (Harker 법) — **미구현 노출됨**
- 현재: `설정 > 불완전 응답 처리`에 `harker` 옵션이 있으나, `ahp_calc`는
  누락 쌍이 있으면 `IncompleteMatrixError`만 던진다. Harker 채움이 없다.
- 목표: Harker(1987) — 누락 쌍을 행 합으로 대치하고 `λ_max` 를 자유도만큼
  보정. `mcdm/linalg.py`에 `harker_fill(matrix, missing_mask)` 추가,
  `derive_weights`가 `incomplete_policy=="harker"`면 이를 경유.
- 효과: 문항 수를 스패닝 트리(n-1개)까지 줄여도 가중치·근사 CR 산출 가능.
  대규모 계층에서 응답 부담 급감.

### 2-B. 그룹 집계: AIJ ↔ AIP 선택의 정식화
- 현재: `settings.aggregation` 로 이미 선택 가능(`aggregate.py`). 문서·UI에서
  차이(개별 CR 확보 vs 단일 합의)를 더 분명히.
- 추가 검토: **가중 기하평균 집계(WGMM)** — 응답자 신뢰도·전문성 가중치를
  받아 AIJ에 반영. `collections`에 `respondent_weight` 필드.

### 2-C. 일관성 지표 확장
- 현재: Saaty CR(`λ_max` 기반) 단일.
- 추가: **GCI**(Geometric Consistency Index, Aguarón & Moreno-Jiménez 2003) —
  기하평균법과 정합적. `weight_method=="geomean"`일 때 CR 대신 GCI 표기.
  `consistency.py`에 `geometric_consistency_index()`.

### 2-D. 척도 민감도
- 현재: 9점/5점 토글.
- 추가: 응답 분포가 척도 상·하한에 몰리면(포화) 경고. 결과 화면 진단 카드.
  (신규 수식 없음, 통계만.)

---

## 3. BWM 트랙

### 3-A. **Bayesian BWM (headline)** — Mohammadi & Rezaei (2020), Omega 96:102087
- 현재: 선형모형 LP(`lp.bwm_linear_weights`, Rezaei 2016). 응답자마다 결정론적
  가중치 벡터 1개 + `ξ`. 그룹은 개인 벡터 기하평균.
- Bayesian BWM: BO/OW 응답을 **다항(multinomial) 관측**으로 보고, 가중치에
  Dirichlet 사전분포를 두어 결합 사후분포를 추정.
  - 개인 수준: 사후 가중치 **분포**(점추정 + 신뢰구간).
  - 그룹 수준: 개인을 하이퍼-Dirichlet로 묶어 **집단 가중치 + 개인별 편차**를
    한 모형에서. 개인 벡터 기하평균보다 통계적으로 정당.
  - **credal ranking**: 기준 i가 j보다 더 중요할 사후확률 → "확신도" 행렬.
    결과 화면에 "A>B (확신 0.87)" 식으로 표기 가능.
- 구현 위치: `mcdm/` 에 `bwm_bayesian.py` (샘플러). `scipy`만으로는 MCMC가
  번거로우니 옵션 2가지:
  1. `numpy` 자체 구현 경량 Gibbs/Metropolis (의존성 0, 반복수 제한).
  2. `pymc` 또는 `numpyro` 추가(의존성 1개, 정석). — **의존성 정책 결정 필요.**
- 플러그인 연결: `BwmPlugin.derive_local`/`aggregate_group`가
  `settings.bwm_solver ∈ {linear, bayesian}` 로 분기. `linear`가 기본 유지.
- 결과 payload: `weights` 는 그대로(사후 평균), `credal` `{i:{j:prob}}` 추가.
- **비용**: 실시간(수집 중) 경로는 `linear` 유지, `bayesian`은 결과 분석 시에만
  돌리는 것을 권장(샘플링 지연).

### 3-B. 비선형 BWM (구간 가중치)
- Rezaei(2015) 원 비선형모형 → 유일해가 아닌 **구간해**. 참고용 상·하한.
- `mcdm/lp.py` 옆에 `bwm_nonlinear_bounds()` (scipy `minimize`, SLSQP).
- 우선순위 낮음 — Bayesian이 불확실성을 더 잘 준다.

### 3-C. 구간·퍼지 BWM
- 언어 변수("약간 더 중요" 등) → 삼각퍼지수 → 퍼지 BWM.
- 응답 UI(1~9 정수 대신 언어 척도)까지 바뀌므로 `RENDERERS.bwm` 재작업 동반.
- 별도 kind (`bwm_fuzzy`)로 두는 편이 깔끔.

---

## 4. 신규 방법 슬롯

각 항목은 §1의 "고정 목록"만 채우면 된다. 대안 평가 전용이 대부분이라
`methods.alternatives` 로 선택(기준 가중치는 AHP/BWM가 산출).

### 4-A. TOPSIS — **가성비 1순위**
- 입력: 기준 전역 가중치(AHP/BWM 산출) + 대안×기준 성능행렬.
- 성능행렬 수집 방식 결정 필요:
  - (a) 응답자가 대안마다 기준별 점수(0~100) 직접 입력 → 새 kind `rating`.
  - (b) 정량 기준은 실측치 업로드(계층 노드에 `measure:"quantitative"`,`unit`
    필드가 이미 있음 — 0단계 마이그레이션에서 백필됨), 정성 기준만 응답.
- 계산: 정규화 → 가중 → 이상해/반이상해 거리 → 근접도 Cᵢ. `mcdm/topsis.py`.
- 뷰: `revealRows`는 기존 재사용, `consoleCells`는 점수 그리드.

### 4-B. 엔트로피 가중치 (객관 가중치)
- 대안×기준 성능행렬만으로 기준 가중치를 **데이터에서** 산출(Shannon 엔트로피).
- 주관(AHP/BWM) 가중치와 **혼합**(λ·주관 + (1-λ)·객관) 옵션 → 결과 화면 비교.
- 응답 불필요 — 성능행렬만 있으면 됨. 4-A의 데이터 수집과 짝.

### 4-C. 직접 평정 / SWING / SMART
- 기준에 100점을 배분하거나 최고 기준=100 기준 상대점수. 문항 1개.
- 가장 가벼운 신규 방법. `kind:"allocate"` 또는 `kind:"vector"`(이미 있음) 재사용.
- BWM·AHP가 부담스러운 소규모·비전문가 패널용.

### 4-D. PROMETHEE II / VIKOR (선택지 확장)
- 아웃랭킹·타협해 계열. 수요가 확인되면. 성능행렬 + 선호함수(PROMETHEE) 파라미터.
- 우선순위 낮음.

---

## 5. 공통(cross-cutting)

- **성능행렬 수집 계층**: 4-A/4-B/4-D가 모두 "대안×기준 점수"를 필요로 함.
  이걸 한 번 설계하면 TOPSIS·엔트로피·PROMETHEE가 동시에 열린다. → 4번 트랙의
  실제 1순위는 "성능행렬 수집 kind" 자체.
- **결과 화면 방법 비교**: 같은 문제를 여러 방법으로 풀었을 때(2.1의 복수 선언)
  순위 상관(Spearman)·Kendall τ 로 "방법 간 일치도" 카드.
- **민감도**: 현재 1기준 흔들기만. 가중치 공간 몬테카를로 → 순위 안정성 %.
- **의존성 정책**: Bayesian BWM(3-A), 퍼지(3-C)에서 `pymc`/`numpyro` 도입 여부가
  분수령. "새 의존성 최소화" 원칙(PLAN.md)과 충돌 — 경량 자체구현 vs 표준
  라이브러리를 항목 착수 시 결정.

---

## 6. 우선순위 · 난이도 · 의존성

| # | 항목 | 가치 | 난이도 | 새 의존성 | 선행 |
|---|---|---|---|---|---|
| 4-A′ | 성능행렬 수집 kind (`rating`) | ★★★ | 중 | 없음 | — |
| 4-A | TOPSIS | ★★★ | 소~중 | 없음 | 4-A′ |
| 4-C | 직접 평정/SMART | ★★ | 소 | 없음 | — |
| 2-A | Harker 불완전 AHP | ★★★ | 중 | 없음 | — (UI 옵션 이미 노출) |
| 4-B | 엔트로피 가중치 | ★★ | 소 | 없음 | 4-A′ |
| 3-A | **Bayesian BWM** | ★★★ | 중~대 | 검토(`pymc`/자체) | — |
| 2-C | GCI 일관성 지표 | ★ | 소 | 없음 | — |
| 5 | 방법 간 일치도·MC 민감도 | ★★ | 중 | 없음 | 복수 방법 실행 |
| 3-B | 비선형 BWM 구간 | ★ | 중 | scipy(있음) | — |
| 3-C | 퍼지 BWM | ★ | 대 | 없음~1 | RENDERERS.bwm 재작업 |
| 4-D | PROMETHEE/VIKOR | ★ | 중 | 없음 | 4-A′ |

## 7. 권고 착수 순서

1. **4-A′ 성능행렬 수집 kind** — TOPSIS·엔트로피·PROMETHEE를 한꺼번에 여는 열쇠.
2. **4-A TOPSIS** + **4-B 엔트로피**(짝) — 주관/객관 가중치 비교까지.
3. **2-A Harker** — 문항 부담을 줄여 채택률을 올리는 실용 개선.
4. **3-A Bayesian BWM** — 의존성 정책 결정 후. 결과 분석 전용 경로로 도입.
5. 이후 2-C · 5 · 나머지는 수요에 따라.
