# PolyDecision 확장 — 배포 시 필요한 작업 (누적)

> 0단계(추상화 도입) 리팩터링을 운영에 반영할 때 **코드 배포 외에** 해야 하는 작업.
> 전체 설계는 `~/.claude/plans/ahp-compiled-shore.md` 참조.
>
> 공통 전제: 단일 워커(인메모리 WS 허브) → 배포는 **코드 반영 + `pm2 restart ahp`** 로
> 진행하며, 그 순간 접속 중이던 실시간 세션은 끊긴다. 실시간 세션 진행 중 배포 금지.

---

## 핵심: 새 DB `mcdm` 로 이전 (구 `ahp` DB는 그대로 보존)

0단계부터 앱은 **`mcdm` DB** 를 쓴다(`app/db.py`, `AHP_DB_NAME` 으로 재정의 가능,
기본값 `mcdm`). 구 `ahp` DB 는 **한 글자도 건드리지 않고** 롤백·이력용으로 남긴다.
`scripts/migrate_ahp_to_mcdm.py` 가 `ahp` → `mcdm` 로 **변환 복사**한다(개명·백필 포함).

## 배포 체크리스트 (0단계 전체, 순서대로)

1. [ ] (선택) `mongodump -d ahp` — `ahp` 는 안 건드리지만 관례상 스냅샷
2. [ ] 실시간 세션이 없는 시간대 확인
3. [ ] 코드 배포 (이 브랜치 머지/pull)
4. [ ] **`ahp` → `mcdm` 변환 복사 1회**
       ```bash
       PYTHONPATH=/home/wcchoi/knpu:/home/wcchoi/knpu/ahp \
         /home/wcchoi/knpu/.venv/bin/python ahp/scripts/migrate_ahp_to_mcdm.py --dry-run  # 확인
       PYTHONPATH=/home/wcchoi/knpu:/home/wcchoi/knpu/ahp \
         /home/wcchoi/knpu/.venv/bin/python ahp/scripts/migrate_ahp_to_mcdm.py            # 실행
       ```
5. [ ] `pm2 restart ahp` — 앱이 `mcdm` 로 붙는다. 기동 시 `ensure_indexes()` 가 `mcdm` 에
       인덱스를 새로 만든다(스크립트가 안 만듦).
6. [ ] 스모크: `/` 302, 관리자 로그인 → 프로젝트 목록 → 설문지 화면 → 결과 화면 로드,
       기존 응답의 가중치·CR 값이 배포 전과 동일한지 1건 대조

- **멱등**: 재실행하면 `mcdm` 문서가 최신 변환으로 `_id` 기준 덮어써진다. 완전 재동기화가
  필요하면 `mcdm` 을 drop 하고 다시 실행.
- 스크립트가 끝에 잔존 검증(`mcdm` 에 `surveys.matrices` / `revision_matrix_id` / `kind` 누락
  0)을 하고 실패 시 non-zero 종료.
- dry-run 기준(현재 `ahp`): projects 7 · hierarchies 22 · surveys 9 · collections 8 ·
  respondents 14 · responses 14 · submissions 13 · results 0 · imports 1 (= 88 docs).

## 롤백

`mcdm` 은 새로 만든 것이고 `ahp` 는 온전하므로 롤백이 단순하다:

1. 코드를 0단계 이전 커밋으로 되돌린다(구 코드는 `_client["ahp"]` 를 본다).
2. `pm2 restart ahp`.
3. `mcdm` DB 는 나중에 정리(drop)하면 된다.

(구 코드로 `mcdm` 을 보게 하거나, 새 코드로 `ahp` 를 보게 하지 말 것 — 스키마가 안 맞는다.
`AHP_DB_NAME` 은 로컬에서 구 DB 를 읽기 전용으로 들여다볼 때만.)

---

## 변환 복사 시 적용되는 스키마 변경 (단계별)

### 1단계 — 식별자 개명

`surveys.matrices` → `surveys.groups`(원소 `matrix_id` → `group_id`),
`respondents.revision_matrix_id` → `revision_group_id`.
`responses`/`submissions` 문서 내용은 **무변경**(바깥 키가 리터럴이 아니라 `parent_uuid` /
`"alt:<uuid>"` 값이라 그대로 `group_id` 값).

### 2단계 — 코드만 (`mcdm/` 공유 코어 + `methods/` 플러그인 골격)

DB 스키마 변화 없음.

### 3·4단계 — `generate_questions` + `surveys.methods` + 플러그인 dispatch

- `surveys.groups[]` 각 원소에 `kind:"pairwise"` · `method:"ahp"` · `scale`(프로젝트
  `settings.scale`) 백필.
- `surveys.methods` 없으면 `{"criteria":{}, "alternatives":"ahp"}` 백필. 이후
  `PUT /api/projects/{id}/survey` body `methods` 로 편집(버전 bump 없음), `resync` 시
  `generate_questions` 가 이 값으로 그룹을 다시 만든다.
- `hierarchies.nodes[]` 각 원소에 `type:"benefit"` · `measure:"qualitative"` · `unit:null`
  백필 (SAW/TOPSIS 등 랭킹 방법용, AHP는 무시).
- 백필이 없어도 코드는 `m.get("kind","pairwise")` / `get_method(None)`(→ AHP 폴백)으로
  견디지만, 데이터 uniform 을 위해 포함.
- 4단계는 **코드만** — `build_results`·라우트의 AHP 직접 호출을 `METHODS[...]` dispatch 로.
  동작·출력 무변경(`build_results` 골든 바이트 동일, 라우트 헬퍼 패리티 9건). 유일한 미세
  차이: what-if 리뷰 차트(`group-eval`)의 동점 항목 정렬 순서(고유벡터 값에선 발생 안 함).

### 5단계 — 코드만

`respond.js` `RENDERERS[kind]` 레지스트리 + `csv_schema.group_item_slots(group)` 하나로
항목/열 순서 통일. DB 조치 없음, 출력 바이트 동일. `docx_export`·`print.js`·`console.js`·
`entry.js` 렌더 루프는 방법별 레이아웃이라 그대로(BWM 때 새로 그림).

> **0단계 코드 완료.** 변환 복사 1회 + `pm2 restart` 로 전체 반영.

---

## 1단계 (BWM) — 진행 중

### 1-1. BWM 계산 코어  *(코드: 완료 / DB·운영: 조치 없음)*

`mcdm/lp.py`(선형모형 LP, scipy.linprog) + `mcdm/bwm_consistency.py`(OR·CR^I·임계값 표) +
`methods/bwm.py`(`BwmPlugin`) 추가, `METHODS["bwm"]` 등록. `KIND_VALIDATORS` 에
`pick_best`/`pick_worst`/`vector` 추가(계약: `(item_id, value)`).

- **순수 추가.** 관리자 UI 로 `surveys.methods` 에 `bwm` 을 배정할 수단이 아직 없고,
  `put_answer` 저장 경로·프론트 렌더러도 없어 BWM 그룹은 실제로 응답할 수 없다. DB 마이그레이션
  불필요, 재기동 불필요(다음 하위 단계와 함께).
- `result_service`: 비-pairwise 그룹은 pairwise 전용 극단값 진단을 건너뛰고, per-respondent
  CR 표시는 `cri` 로 폴백(방어적, 현재 도달 불가).
- 검증: `ahp/tests/check_methods_bwm.py` (7건) + `check_methods_ahp.py` 회귀(9건) + 골든 동일.

### 1-2. 저장 경로 일반화  *(코드: 완료 / DB·운영: 조치 없음)*

`put_answer`(respond·entry)가 `kind` 로 dispatch: `KIND_VALIDATORS[kind](body) → (item_id, value)`
→ `answers[group_id][item_id] = value`. 진행률은 `csv_schema.group_item_count(group)`
(pairwise n(n-1)/2, bwm 2n)로 계산. **pairwise 는 바이트 동일**(골든·패리티·9+9건).
`section_snapshot` 은 비-pairwise 그룹의 쌍 진단을 건너뛴다.

- 아직 BWM 그룹을 만들 관리자 UI(1-4)도 렌더러(1-3)도 없어 실제로 도달 불가.
  DB 마이그레이션·재기동 불필요.
- 검증: `check_methods_bwm.py` (9건 — +저장 경로 시뮬레이션) + `check_methods_ahp.py` (9건) + 골든 동일 + uvicorn 부팅.

### 1-3. BWM 응답 렌더러 + 재개/what-if 배선  *(코드: 완료 / DB·운영: 조치 없음)*

- `respond.js`: `RENDERERS[kind]` 계약 일반화(`renderBody`/`isComplete`/`answered`/`total`/
  `overrides`). `RENDERERS.bwm` — Best/Worst 선택 버튼 + BO/OW 1~9 눈금 벡터. `bwmClickHandler`
  (설문·리뷰 컨테이너에 위임). `renderMatrixPage`·`matrixComplete`·`updateProgress`·
  `renderReviewPairs`·`enterReview` 가 렌더러에 dispatch.
- 백엔드: `_build_matrices_view` 비-pairwise 는 `pairs:[]`; `_resolve_display_answers` 는
  비-pairwise 답을 그대로 통과(재개 시 유실 방지); `group-eval` 은 overrides 적용을 플러그인에
  위임 + `locus` 반환; `put_answer` 는 Best/Worst 변경 시 BO/OW 무효화(respond·entry).
  `Consistency.value` 속성(AHP CR / BWM CR^I) 도입.
- `respond.css`: `.bwm-*`.
- **pairwise 무변경**(골든·패리티 9+9). BWM 그룹을 만들 관리자 UI(1-4)가 없어 라이브 E2E 는
  1-4 이후. 위젯 렌더는 헤드리스(라이트·다크) 확인.
