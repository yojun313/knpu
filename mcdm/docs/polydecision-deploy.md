# PolyDecision 배포 및 DB 운영

## DB 연결과 데이터베이스 선택

- MongoDB 접속 정보, SSH 터널과 동기·비동기 클라이언트는 `system/db/connection.py`에서 관리합니다. DB 이름 접두사는 `system/db/names.py`에서 관리합니다.
- 서비스는 `system.db`의 `client` 또는 `get_async_client()`를 사용합니다.
- DB·컬렉션 이름은 `system/db/mcdm.py`, 인덱스 초기화·DB 헬퍼는 `mcdm/app/db.py`에서 관리합니다.
- PolyDecision은 실행 모드와 관계없이 **`knpu-mcdm` DB**를 사용합니다. 별도 개발 DB나 DB 이름 재정의 환경변수는 사용하지 않습니다.
- `MODE`는 서비스 주소·포트 구분에 사용하며 데이터베이스를 분리하지 않습니다.
- `ahp` 방법명, 기존 브라우저 저장소 키와 `ahp_db` 호환 별칭은 유지합니다. `ahp_db`도 `knpu-mcdm`을 가리킵니다.

## DB 이름 규칙

모든 애플리케이션 DB는 `knpu-` 접두사를 사용합니다. MongoDB 인증 DB(`MONGO_AUTH_DB`)는 애플리케이션 DB 이름과 별개입니다.

코드는 준비된 DB 이름을 참조하며, DB 이름 변경을 위한 데이터 복사·이전·삭제를 자동으로 수행하지 않습니다.

## 배포 확인

1. 실시간 세션이 진행되지 않는 시간에 코드를 반영합니다. 현재 WebSocket 허브는 프로세스 메모리를 사용합니다.
2. 공통 MongoDB 접속 환경변수를 확인하고 해당 PolyDecision 프로세스를 재시작합니다.
3. 로그인, 프로젝트 목록, 설문 응답과 결과 화면을 확인합니다. 인덱스는 앱 시작 시 기존 정의로 초기화합니다.
4. 다른 모드로 실행하는 프로세스도 같은 데이터를 사용하므로 변경 내용이 함께 반영됩니다.

## 이전 AHP 자료의 변환 도구

기존 `ahp` 자료를 변환할 때만 `mcdm/scripts/migrate_ahp_to_mcdm.py`를 명시적으로 실행합니다. 일반 배포 과정에서 실행하는 작업은 아닙니다. 대상은 항상 `knpu-mcdm`이며, 원본 자료는 삭제하지 않습니다.

```bash
cd /home/yojun/knpu
.venv/bin/python mcdm/scripts/migrate_ahp_to_mcdm.py --dry-run
```

`--dry-run`은 조회만 수행합니다. 옵션 없이 실행하면 변환 자료를 대상 DB에 `_id` 기준으로 반영합니다.

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

### 1-4. 관리자 방법 선택 UI  *(코드: 완료 / DB·운영: 조치 없음)*

- 설문지 편집 화면(`survey_editor.js`): 각 기준 그룹 카드에 **"가중치 산출 방법" 드롭다운**
  (AHP / BWM). 변경 시 `PUT /api/projects/{id}/survey {methods:{criteria, alternatives}}`.
- `survey_routes.update_survey`: `methods` 가 오면 **그 자리에서** 현재 계층으로 `groups` 를
  다시 만든다(버전 bump 없음 — `group_id`/`child_uuids` 는 그대로, `kind`/`method`/
  `question_text` 만 갱신). 종류(kind)가 바뀐 그룹은 `responses`·`submissions` 에서
  `answers.<group_id>` 를 `$unset`(형식이 달라 기존 응답 무의미). 응답 `cleared_answers` 반환.
  종류가 그대로면 연구자가 다듬은 질문 문구는 유지.
- **여기서부터 BWM 을 실제로 만들 수 있다** — 노드를 BWM 으로 바꾸고 발행하면 응답자 화면(1-3)에
  BWM 흐름이 나온다.
- 검증: `check_methods_bwm.py` 10건(+혼합방법 `build_results` 파이프라인 — root=AHP·c1=BWM
  전역가중치 합성) + `check_methods_ahp.py` 9건 + 골든 동일 + `node --check` + 부팅.

### 1-5. 오프라인 BWM — CSV 반입 + 인쇄/Word 양식  *(코드: 완료 / DB·운영: 조치 없음)*

- `csv_schema.group_import_slots(group)`: 반입 열 슬롯을 kind별로 — pairwise `n(n-1)/2` 쌍 /
  bwm `best·worst + BO×n + OW×n` (`2+2n`).
- `entry_routes.import_csv`: 슬롯 kind별 파싱(pairwise / pick_best·worst(기준 이름 또는
  1-base 번호 → uuid) / vector 1~9). `get_grid` 는 비-pairwise 를 `pairs:[]` 로.
- `export-template.csv` BWM 열 헤더, `sheet_export` BWM tidy 행, `print.js`/`docx_export`
  BWM 인쇄·Word 양식(Best/Worst 선택 줄 + 1~9 눈금표 2개, Q번호 = CSV 열 순서).
- `entry.js`: 비-pairwise 그룹은 "CSV 반입으로 입력" 안내.

### 1-6. 결과 화면 BWM 표시  *(코드: 완료 / DB·운영: 조치 없음)*

- `build_results` 추가 키: `group_kinds`, `bwm`({gid:{bw_distribution, per_respondent:
  {rid:{cri, cri_threshold, or}}}}). 기존 키 바이트 동일.
- `result.js`: 개인별 일관성 표가 방법별 — BWM 은 응답자별 **CR^I 임계값**((n,척도) 표)로
  판정 + **순서 일관성(OR)** 열. `renderBwmDistribution` — Best/Worst 지목 분포 막대.
- `result.html`/`result.css`: `#bwmDistCard` + `.bwm-dist-*`.

> **1단계(BWM) 완료.** 온라인·실시간·오프라인 3모드 + 결과 화면. 수집 계층 코드는
> `KIND_VALIDATORS`/`group_item_count` 배선 외 무수정(설계 합격 기준 충족).
