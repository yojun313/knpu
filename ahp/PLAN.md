# 웹 기반 AHP 시스템 — 구현 계획서

> KNPU 연구 시스템(FastAPI · MongoDB) 위에 올리는 AHP 서비스.
> 모든 구현은 `knpu/ahp/` 아래. 외부 서비스(Google Docs 등) 사용하지 않음.

> **상태: 1~5단계 전부 구현·자체 테스트 완료.** 계산 엔진(고유벡터·CR·AIJ/AIP·
> Kendall's W·민감도), 계층 설계, 설문지 편집, 오프라인/온라인/실시간 수집,
> 웹소켓 실시간 반영, 결과 통합 분석, Word/Excel/CSV 내보내기, A4 인쇄까지
> 실서버 기동 + curl/CDP 헤드리스 브라우저로 전부 검증됨. 남은 건 12.5절의
> 배포 체크리스트(pm2/nginx/DNS, 사용자가 직접 적용)뿐.

---

## 1. 범위 — 3가지 조사 모드

| 모드 | 설문지 배포 | 응답 입력 주체 | 실시간 |
|---|---|---|---|
| **오프라인** | 웹에서 만들어 인쇄(A4/Word) | **관리자**가 종이 응답을 웹에 입력 | ✗ |
| **온라인 · 일반** | 링크 배포 | 응답자 본인이 웹에서 | ✗ |
| **온라인 · 실시간** | 링크 배포(세션 코드) | 응답자 본인이 웹에서 | ✓ |

세 모드는 **설문지 정의(계층 + 문항)를 공유**한다. 한 번 만든 설문지를 인쇄해서 오프라인으로 돌리고,
동시에 온라인으로도 배포할 수 있어야 한다. 즉 `survey` 하나에 `mode`가 여러 개 붙을 수 있는 구조가 아니라,
**`survey`는 정의이고 `collection`(수집 회차)이 모드를 갖는다.**

```
project (연구)
 └ hierarchy (계층, 버전별)
    └ survey (설문지 정의, 버전별)
       ├ collection#1  mode=offline   ← 종이, 관리자 입력
       ├ collection#2  mode=online    ← 링크 배포
       └ collection#3  mode=realtime  ← 실시간 세션
```

이렇게 하면 **같은 설문지로 받은 오프라인/온라인 응답을 한 분석에 합칠 수 있다.** 중요한 요구사항.

---

## 2. 디렉터리 구조

기존 앱(`network`, `kemkim`, `statistics`)의 규약을 그대로 따른다.

```
knpu/ahp/
├── run.py                     # uvicorn, port 8010, workers=1 (필수)
├── pyproject.toml             # openpyxl 추가 (아래 3절)
├── PLAN.md
└── app/
    ├── main.py                # FastAPI 앱, 미들웨어, 정적 마운트
    ├── config.py              # 환경변수, MODE
    ├── db.py                  # motor(async) + system.db(sync) 두 갈래
    ├── routes/
    │   ├── __init__.py        # api_router 조립
    │   ├── page_routes.py     # HTML 페이지 서빙
    │   ├── project_routes.py  # 프로젝트/계층 CRUD
    │   ├── survey_routes.py   # 설문지 정의 CRUD, 배포
    │   ├── respond_routes.py  # 응답자용 (공개 경로)
    │   ├── entry_routes.py    # 오프라인 응답 입력
    │   ├── result_routes.py   # 분석 결과
    │   ├── export_routes.py   # Word/Excel/CSV
    │   └── ws_routes.py       # 웹소켓
    ├── services/
    │   ├── ahp_calc.py        # 가중치·CR·집계 (순수 함수, numpy)
    │   ├── consistency.py     # 비일관성 진단·수리 제안
    │   ├── aggregate.py       # AIJ/AIP 그룹 집계, 합의도
    │   ├── hub.py             # 인메모리 웹소켓 허브
    │   ├── survey_service.py  # 설문지 버전·변경 분류
    │   ├── docx_export.py     # python-docx
    │   └── sheet_export.py    # Excel/CSV
    ├── models/                # pydantic 스키마
    └── static/
        ├── css/  (admin.css, respond.css, print.css)
        ├── js/   (admin.js, designer.js, respond.js, realtime.js)
        ├── img/  (lab_logo.png)
        ├── admin.html         # 관리자 (상단바 있음)
        ├── designer.html      # 계층/설문지 편집
        ├── console.html       # 실시간 운영 콘솔
        ├── respond.html       # 응답자 (상단바 없음)
        └── print.html         # 인쇄용 설문지
```

---

## 3. 배포

| 항목 | 값 |
|---|---|
| 포트 | **8010** (8000~8009 점유, 8004·8005 포함) |
| 도메인 | `ahp.knpu.re.kr` |
| 워커 | **`workers=1` 필수** — 인메모리 웹소켓 허브가 상태를 가짐 |
| pm2 | `ecosystem.config.js`에 **반드시 등록**, `watch: false` |
| nginx | `manager.knpu.re.kr`의 `/progress/` 블록 복제 (웹소켓 업그레이드 + `proxy_read_timeout 86400`) |

### 의존성 추가
- **`openpyxl`** — 현재 venv에 **없음**. xlsx 내보내기에 필요 (pandas가 내부적으로 사용)
- `python-docx` 1.2.0 — 있음 ✓
- `numpy`, `scipy` — 있음 ✓ (고유벡터 계산)
- `motor` — 있음 ✓ (async MongoDB)

### `run.py`
```
uvicorn.run("app.main:app", host="0.0.0.0", port=8010,
            workers=1, timeout_keep_alive=86400)
```
`timeout_keep_alive`는 웹소켓 장시간 유지를 위해 `manager/web`과 동일하게.

---

## 4. 데이터 모델 — MongoDB `ahp` DB

### 4.1 접근 방식 (중요)

두 갈래로 나눈다.

- **`system.db` (동기 pymongo)** — `user_db`, `user_logs_db`. HTTP 라우트에서만 사용.
- **motor (async)** — `ahp` DB 전용. **웹소켓 경로는 반드시 이쪽.**

> 웹소켓 핸들러에서 동기 pymongo를 호출하면 워커가 1개이므로 **접속자 전원이 함께 멈춘다.**
> 이게 이 설계의 단일 실패점이다.

### 4.2 컬렉션

**`projects`** — 연구 단위
```
_id, owner_uid, title, description, status(draft|active|closed),
settings: {
  scale: 9|5,                      # 척도
  aggregation: "AIJ"|"AIP",        # 집계 방식
  weight_method: "eigen"|"geomean",# 가중치 도출법
  cr_threshold: 0.1,
  allow_incomplete: bool
},
created_at, updated_at
```

**`hierarchies`** — 계층 트리(버전별 스냅샷)
```
_id, project_id, version,
nodes: [ { uuid, parent_id|null, name, description, order, level } ],
created_at
```
> `uuid`는 노드 생성 시 부여하고 **절대 바뀌지 않는다.** 응답은 이 uuid로 저장한다.
> 이름·순서·설명이 바뀌어도 기존 응답이 살아남는 근거.

**`surveys`** — 설문지 정의(배포 단위)
```
_id, project_id, hierarchy_version, version,
title, intro_text, consent_text,      # 응답자에게 보일 안내·동의 문안
node_descriptions: { <node_uuid>: "설명" },
matrices: [ { matrix_id, parent_uuid, child_uuids[], question_text } ],
status(draft|published|closed), created_at, updated_at
```
> `matrices`는 계층에서 자동 생성(부모마다 1개). `matrix_id`도 안정 ID.

**`collections`** — 수집 회차 (모드가 여기 붙는다)
```
_id, survey_id, survey_version, mode(offline|online|realtime),
label,                                # "1차 전문가 패널" 등
access_token,                         # 온라인 배포 링크의 토큰
status(open|closed), round,           # 델파이 라운드
opened_at, closed_at
```

**`respondents`** — 참여자(익명)
```
_id, collection_id, code_hash, label,  # label = "참여자 A-17"
source(web|manual),                    # manual = 관리자가 종이 입력
attributes: { field, career_years },   # 선택적 층화 변수
consent_at, created_at
```

**`responses`** — 작업 중 응답(가변)
```
_id, collection_id, respondent_id, survey_version,
answers: { <matrix_id>: { <pair_id>: { value, updated_at } } },
client_seq, progress, updated_at
```
> `pair_id` = `"<uuid_i>:<uuid_j>"` (사전순 정렬로 정규화). 역수는 저장하지 않고 계산 시 유도.

**`submissions`** — 제출 스냅샷(불변)
```
_id, collection_id, respondent_id, round, survey_version,
answers(동결), submitted_at
```
> 절대 덮어쓰지 않는다. 델파이 라운드 간 수렴 분석의 근거.

**`results`** — 계산 캐시
```
_id, collection_id, scope("individual"|"group"), respondent_id|null,
local_weights: { <matrix_id>: { <uuid>: w } },
global_weights: { <uuid>: w },
cr: { <matrix_id>: value },
consensus: { kendall_w, cv_by_pair },
computed_at, survey_version
```

**`imports`** — 종이/CSV 반입 이력
```
_id, collection_id, filename, uploaded_by, row_count,
validation: { errors[], warnings[] }, created_at
```

### 4.3 인덱스
```
responses     : (collection_id, respondent_id) UNIQUE
submissions   : (collection_id, respondent_id, round)
respondents   : (collection_id, code_hash) UNIQUE
collections   : (access_token) UNIQUE sparse
surveys       : (project_id, version)
```

---

## 5. 인증과 권한

### 5.1 두 부류
- **연구자/관리자** — 기존 중앙 JWT(`system.auth`). 미인증 시 `knpu.re.kr/login` 리다이렉트.
  라우트에서 `request.scope["state"]["user"]` → `{uid, name, role}`
- **응답자** — **익명.** 로그인 없음. 배포 링크 토큰 + 접속 코드로 식별.

### 5.2 공개 경로
```
app.add_middleware(AuthMiddleware, extra_public_paths=[
    "/r/",            # 응답자 페이지
    "/api/respond/",  # 응답자 API
    "/static/",
])
```

### 5.3 웹소켓 인증 — 함정

> `AuthMiddleware.__call__`은 `scope["type"] != "http"`이면 **그대로 통과시킨다.**
> 즉 **웹소켓은 미들웨어 인증을 전혀 거치지 않는다.**
> 엔드포인트 안에서 직접 검증해야 하고, 빠뜨리면 누구나 관리자 채널에 붙을 수 있다.

- 관리자 소켓(`/ws/console/{collection_id}`): 연결 시 쿠키의 `session` JWT를 직접 디코드해 검증.
  `decode_token`은 동기이므로 **`run_in_threadpool`로 감싼다.**
- 응답자 소켓(`/ws/respond/{collection_id}`): 접속 코드로 발급한 단기 토큰을 첫 메시지로 받아 검증.
  실패 시 `close(code=1008)`.

### 5.4 익명 식별 방식
- 관리자가 참여자 수만큼 **접속 코드**를 사전 생성 (예: `K7M-2QD`) → 현장 배부
- 응답자는 코드만 입력 → 서버는 `code_hash`로 식별, 화면에는 `참여자 A-17`만 노출
- 코드-실명 매핑은 **시스템에 저장하지 않는다** (배부 기록은 시스템 밖)
- 같은 코드로 **재접속·이어쓰기·다음 라운드 참여** 가능
  (브라우저 토큰만 쓰면 기기 변경·캐시 삭제 시 응답자를 잃는다)

---

## 6. 화면과 라우트

### 6.1 관리자 화면 (상단 네비게이션 바 **있음**)

| 경로 | 화면 | 기능 |
|---|---|---|
| `/` | 프로젝트 목록 | 생성·삭제·복제, 상태 필터 |
| `/design/{project_id}` | **계층 설계** | 트리 편집(드래그·인라인 수정), 브레인스토밍 패드, 되돌리기 |
| `/survey/{project_id}` | **설문지 편집** | 문항 문구, 계층별 설명, 안내·동의 문안, 미리보기 |
| `/collect/{project_id}` | **수집 관리** | 회차 생성(모드 선택), 링크·코드 발급, 진행 현황 — 한 프로젝트에 오프라인/온라인/실시간 collection이 동시에 여러 개 있을 수 있어 project 기준 |
| `/entry/{collection_id}` | **오프라인 입력** | 종이 응답을 격자로 입력, CSV 반입 — collection 기준(그 회차 하나) |
| `/console/{collection_id}` | **실시간 콘솔** | 참여자별 진행률·CR, 분포·극단값, 실시간 문항 수정 — collection 기준 |
| `/result/{project_id}` | **분석 뷰어** | 가중치(지역/전역), CR, 합의도, 민감도, 그림 내보내기 — 오프라인+온라인 응답을 한 분석에 합치려면(1절) project 기준이어야 함. `?collection_id=`로 특정 회차만 드릴다운 가능 |
| `/print/{survey_id}` | 인쇄 미리보기 | A4 레이아웃 |

### 6.2 응답자 화면 (상단 네비게이션 바 **없음**)

| 경로 | 화면 |
|---|---|
| `/r/{access_token}` | 진입 — 연구 안내, 통계 비밀유지 고지, **동의** |
| `/r/{access_token}/code` | 접속 코드 입력 |
| `/r/{access_token}/survey` | 응답 — 쌍대비교, 진행률, 연결 상태 |
| `/r/{access_token}/done` | 제출 완료 (실시간이면 대기 화면) |

### 6.3 주요 API

```
# 프로젝트·계층
GET    /api/projects
POST   /api/projects
GET    /api/projects/{id}/hierarchy
PUT    /api/projects/{id}/hierarchy        # 새 version 생성

# 설문지
POST   /api/surveys                        # 계층에서 matrices 자동 생성
PUT    /api/surveys/{id}                   # version += 1, 변경 분류
POST   /api/surveys/{id}/publish

# 수집 회차
POST   /api/collections                    # mode 지정, access_token 발급
POST   /api/collections/{id}/codes         # 접속 코드 N개 생성
POST   /api/collections/{id}/close

# 오프라인 입력
POST   /api/entry/{collection_id}/respondent   # 종이 응답자 1명 추가
PUT    /api/entry/{collection_id}/answers      # 격자 입력 저장
POST   /api/entry/{collection_id}/import       # CSV 반입 + 검증

# 응답자 (공개)
POST   /api/respond/{token}/consent
POST   /api/respond/{token}/code               # 코드 검증 → 단기 토큰
GET    /api/respond/{token}/survey
PUT    /api/respond/{token}/answer             # 비실시간 저장(HTTP 폴백)
POST   /api/respond/{token}/submit

# 결과·내보내기
GET    /api/results/{collection_id}
GET    /api/results/{collection_id}/sensitivity
GET    /api/export/{id}/survey.docx            # Word 설문지
GET    /api/export/{id}/package.xlsx           # 재현 패키지
GET    /api/export/{id}/responses.csv
```

---

## 7. 실시간 아키텍처

### 7.1 구조
워커 1개 → **파이썬 딕셔너리가 곧 공유 상태.** Redis·pub/sub 불필요.
`manager/web`(포트 8080, `workers=1`, 인메모리 `clients`)이 이미 같은 구조로 운영 중 — 검증된 선례.

```python
# services/hub.py — 개념
_rooms: dict[str, set[WebSocket]] = {}     # collection_id → 소켓들
_roles: dict[WebSocket, str] = {}          # 소켓 → "admin"|"respondent"

async def publish(collection_id, event, payload, only=None): ...
```
> `publish()` 하나로 감싸 둔다. 나중에 워커를 늘려야 하면 이 함수 내부만 Redis pub/sub으로
> 교체하면 되고 호출부는 건드리지 않는다.

### 7.2 웹소켓 이벤트

**클라이언트 → 서버**
| 이벤트 | 페이로드 | 비고 |
|---|---|---|
| `auth` | `{token}` | 연결 직후 1회 |
| `answer` | `{matrix_id, pair_id, value, client_seq}` | 디바운스 200~300ms |
| `resync` | `{last_seq, known_version}` | 재연결 직후 |
| `ping` | — | 30s 주기 |

**서버 → 클라이언트**
| 이벤트 | 대상 | 페이로드 |
|---|---|---|
| `ack` | 해당 응답자 | `{client_seq}` |
| `survey.patch` | 응답자 전원 | `{version, changes[], invalidated[]}` |
| `resync.result` | 해당 응답자 | `{version, server_answers, missed_changes[]}` |
| `progress` | 관리자 | `{respondent_id, progress, cr}` |
| `stats` | 관리자 | `{distribution, outliers, group_weights}` |

### 7.3 관리자 수정 → 클라이언트 반영 흐름
```
1. 관리자가 콘솔에서 문항 수정
2. 서버: survey version += 1, 변경 종류 분류
3. 서버: publish(collection_id, "survey.patch", {변경분만})
4. 응답자: 해당 영역만 부분 갱신 + "이 항목이 수정되었습니다" 표시
   → 페이지 새로고침 금지. 작성 중이던 다른 입력이 날아간다.
5. 무효화된 문항만 재응답 유도
```

### 7.4 변경 종류별 무효화 범위

| 변경 | 기존 응답 | 응답자 화면 |
|---|---|---|
| 설명·문구 수정, 이름 변경 | 전부 유지 | 변경 표시만 |
| 형제 순서 변경 | 전부 유지 | 재정렬 |
| 하위 기준 **추가** | 해당 행렬 부분 유지 | 새 쌍만 추가 질문 |
| 하위 기준 **삭제** | 해당 쌍만 폐기 | 나머지 유지 |
| 노드 이동(부모 변경) | 양쪽 행렬 무효 | 두 행렬 재응답 |

폐기된 응답도 **삭제하지 않고 보존**한다(되돌리기·연구 기록).

### 7.5 재연결·오프라인 (현장 필수)
한 방에 30~50명이 AP 하나를 공유 → **웹소켓은 반드시 끊긴다.**
- 미전송 입력을 **`localStorage` 큐**에 보관 (탭 닫아도 생존)
- 지수 백오프 재연결 (1s→2s→4s… 최대 30s) + 지터
- 재연결 시 `resync` 왕복으로 놓친 변경분과 서버 보유 응답을 동기화
- 연결 상태 상시 표시(연결됨 / 재연결 중 / 오프라인 — 입력은 계속 가능)
- 웹소켓 차단 망 대비 **HTTP 폴백 저장 경로** 유지

### 7.6 저장 규칙
- `$set`으로 **부분 갱신** (문서 전체 재작성 금지 — 동시 수정이 서로를 덮어씀)
- `client_seq`로 순서 보장, 낮은 seq가 늦게 오면 무시
- `ack` 받은 항목만 클라이언트 로컬 큐에서 제거

---

## 8. AHP 계산 엔진 (`services/ahp_calc.py`)

순수 함수로 작성 — DB·웹소켓 의존 없음. 단위 테스트 대상.

### 8.1 가중치 도출
- **고유벡터법(기본)**: `numpy.linalg.eig` → 최대 고유값의 고유벡터, 정규화
- **행 기하평균법**: 각 행의 기하평균 → 정규화
- 둘 다 산출해 비교 가능하게

### 8.2 일관성비 CR
```
CI = (λmax − n) / (n − 1)
CR = CI / RI[n]
```
RI 표 (Saaty):
```
n :  1     2     3     4     5     6     7     8     9    10    11    12    13    14    15
RI: 0.00  0.00  0.58  0.90  1.12  1.24  1.32  1.41  1.45  1.49  1.51  1.48  1.56  1.57  1.59
```
> **n ≤ 2는 CR이 정의되지 않는다** (항상 완전 일관). 예외 처리 없으면 0으로 나누기 발생.

### 8.3 집계 (`services/aggregate.py`)
- **AIJ** — 쌍대비교 값을 응답자 간 **기하평균**으로 합친 뒤 가중치 도출
- **AIP** — 개인별 가중치를 먼저 구하고 그 다음 합침

> **평균은 반드시 기하평균.** 산술평균을 쓰면 역수 관계가 깨진다
> (`mean(a_ij) ≠ 1/mean(a_ji)`). AHP에서 산술평균은 오류이고, 구현에서 가장 실수하기 쉬운 지점.

### 8.4 비일관성 진단 (`services/consistency.py`)
CR 값만 보여주면 현장에서 아무것도 못 한다. **어느 판단이 문제인지 지목해야 한다.**
- 일관성 행렬 `w_i/w_j`와 실제 `a_ij`의 편차를 계산
- 편차 상위 3개 쌍을 지목하고 **권장값 제시**
- 실시간 델파이의 실질적 가치가 여기 있다

### 8.5 그룹 지표
- 쌍별 변동계수(CV), **Kendall's W** — 라운드 간 수렴도
- 극단값: 쌍별 로그 스케일 **중앙값·MAD(중앙값 절대편차) 기반 수정 z-점수**(임계값 3.5, `find_outliers()` 구현됨). 평균·표준편차 기반 z-점수는 작은 패널(5~15명)에서 극단값 자신이 표준편차를 부풀려 스스로를 가리는 약점이 있어 채택하지 않았다

### 8.6 가중치 표기
- **지역 가중치** — 같은 부모 아래에서의 상대 중요도
- **전역 가중치** — 루트까지의 곱
- 화면에 **둘 다 표시** (혼동하면 해석이 틀어진다)

### 8.7 민감도 분석
상위 기준 가중치를 ±x% 변화시켰을 때 순위 역전 여부. 심사에서 자주 요구됨.

---

## 9. 내보내기

| 형식 | 라이브러리 | 내용 |
|---|---|---|
| **Word (.docx)** | `python-docx` ✓ | 설문지 — 표지, 안내·동의문, 계층도, 쌍대비교 표 |
| **Excel (.xlsx)** | `openpyxl` **추가 필요** | 재현 패키지 — 계층·원자료·설정·결과·CR 시트 분리 |
| **CSV** | 표준 | 응답 원자료 (반입용과 동일 스키마) |
| 인쇄 (A4) | CSS | `@page` + `page-break-inside: avoid` |

### 인쇄 요구
- **"같은 계층의 페이지 넘김 자제"** → 각 비교 행렬 블록에 `page-break-inside: avoid`
- 별도 PDF 엔진(WeasyPrint 등) **도입하지 않음** — 브라우저 인쇄로 충족되고,
  한글 폰트 임베딩 문제를 새로 떠안을 이유가 없다
- **인쇄 레이아웃과 CSV 열 구조를 1:1로 맞춘다.** 어긋나면 반입 때마다 손으로 매핑해야 한다

---

## 10. 테마 통합

### 10.1 관리자 화면 — 기존과 동일
`<head>`에 FOUC 방지 스니펫 + `/shared-ui/theme.css` + `/shared-ui/theme.js`,
`.top-header` 마크업에 `#themeSettingsBtn` 포함. 기본/글래스/애플/뉴모피즘/메시 + 다크 전부 지원.

`main.py`에 마운트:
```
SHARED_UI_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "system", "ui")
app.mount("/shared-ui", NoCacheStaticFiles(directory=SHARED_UI_DIR), name="shared-ui")
```

### 10.2 응답자 화면 — 테마 시스템 자체를 배제 (결정됨)
관리자 화면과 완전히 분리된 스타일시트를 쓴다. `/shared-ui/theme.css`, `theme.js`를 **로드하지 않고**,
5종 테마 선택지도 없다. 오직 시스템 설정을 따르는 라이트/다크 두 가지만 존재한다.

```css
:root{ /* 라이트 토큰 */ }
@media (prefers-color-scheme: dark){ :root{ /* 다크 토큰 재정의 */ } }
```
- `.top-header`, 테마 설정 버튼(⚙) **없음** — 5절 요구사항
- 응답자 화면 전용 토큰 셋(`--r-bg`, `--r-surface`, `--r-ink`, `--r-muted`, `--r-accent`,
  `--r-border`, `--r-danger`)을 새로 정의. 관리자 화면의 `--sidebar-*` 토큰과 이름 충돌 없게 분리
- **모바일 퍼스트**: 기준 뷰포트는 360~430px, 터치 타깃 44px 이상, 쌍대비교 슬라이더는
  손가락 드래그 전용 큰 컨트롤. `min()`/`clamp()`로 큰 화면까지 자연 확장 — 별도 데스크톱
  브레이크포인트를 크게 신경 쓰지 않아도 되게 설계 (모바일이 기본값)
- 다크 판정은 오직 `prefers-color-scheme`. 쿠키·로컬스토리지로 응답자가 강제 전환할 수단은 없음
  (요청사항 그대로: "시스템설정에 따라 라이트/다크모드만")

### 10.3 favicon
`/shared-ui/favicon.ico` (이미 배치됨)

---

## 11. 방법론 결정 — 기본값 확정 + 전부 프로젝트 설정으로 노출

**기본값은 코드에 상수로 박지 않는다.** `projects.settings`에 전부 필드로 넣고,
연구자가 **프로젝트 생성/설정 화면에서 웹으로 직접 바꿀 수 있게** 한다.
아래는 "결정을 안 내려도 되게" 만든 것이 아니라 **초기값(default)의 근거**다.

| # | 설정 키 | 선택지 | 기본값 | 근거 |
|---|---|---|---|---|
| 1 | `aggregation` | `AIJ` / `AIP` | **`AIP`** | 개인 가중치를 먼저 구하므로 **개별 응답의 CR을 그 자리에서 바로 확보**할 수 있다. 실시간 델파이에서 "이 사람 판단이 비일관적이다"를 즉시 알려주려면 AIP가 구조적으로 필요 — AIJ는 판단을 먼저 합쳐버려서 개인별 CR을 별도로 한 번 더 계산해야 한다 |
| 2 | `weight_method` | `eigen` / `geomean` | **`eigen`** | Saaty 표준. CR 계산도 고유벡터의 λmax에서 바로 나와 일관됨. 행 기하평균은 참고값으로 병행 산출 |
| 3 | `alt_layer` | `off` / `on` | `off` | 기준 가중치만이 기본, 필요 시 대안 계층 추가 |
| 4 | `incomplete_policy` | `block` / `allow_partial` / `harker` | `block` | 불완전 행렬은 제출 차단, 완료율만 진행 중 표시 |
| 5 | `scale` | `9` / `5` | `9` | Saaty 9점 표준, 5점 축약형은 옵션 |
| 6 | `cr_threshold` | 0~1 | `0.1` | Saaty 권고치 |
| 7 | `cr_action` | `warn` / `block` | `warn` | 초과 시 재고 유도, 제출 자체는 막지 않음(연구자가 나중에 필터링 가능하도록 데이터는 남긴다) |

이 7개는 **`GET/PUT /api/projects/{id}/settings`** 로 전부 읽고 쓴다. 관리자 화면의
"프로젝트 설정" 패널에서 드롭다운/토글로 노출 — 코드에 새 if문을 추가하지 않고 값만 바꾼다.
단, **설문 배포(`collection` open) 이후에는 1·2·3·5번은 잠근다** — 진행 중 방법론이 바뀌면
이미 받은 응답과 이후 응답이 다른 방식으로 계산되어 결과가 오염된다. 잠금 해제는
"새 collection으로 다시 시작"만 허용.

---

## 12. 구현 순서

### 1단계 — 뼈대 + 계층 설계 + 인쇄
- `main.py`, `run.py`, `db.py`(motor), nginx, ecosystem 등록
- 프로젝트 CRUD, 계층 트리 편집기, 브레인스토밍 패드
- 설문지 편집, A4 인쇄, Word 내보내기
- **이 시점에 오프라인 AHP 연구를 수행할 수 있다**

### 2단계 — 오프라인 입력 + 계산 엔진
- 종이 응답 격자 입력, CSV 반입·검증
- `ahp_calc.py`, `consistency.py`, `aggregate.py` (+ 단위 테스트)
- 분석 뷰어(지역/전역 가중치, CR), Excel 재현 패키지
- **여기서 방법론(11절 1·2번)이 코드로 고정된다**

### 3단계 — 온라인 일반 설문
- 배포 링크·접속 코드, 동의 화면, 응답자 UI(상단바 없음)
- HTTP 저장 경로, 제출·라운드

### 4단계 — 실시간 델파이
- 웹소켓 허브, 콘솔, 실시간 문항 수정 + `survey.patch`
- 재연결·오프라인 큐, 실시간 CR·극단값

### 5단계 — 분석 심화
- 민감도 분석, Kendall's W·수렴도, 논문용 그림 내보내기

---

## 12.5 배포 체크리스트 (수동 적용 필요 — pm2/nginx는 사용자가 직접 관리)

코드는 `knpu/ahp/`에 전부 구현·검증 완료됐다. 실제로 도메인에 뜨게 하려면 아래
두 가지를 수동으로 적용해야 한다(이 세션에서는 건드리지 않았다).

### `/home/lab/ecosystem.config.js`에 항목 추가
기존 network/kemkim/statistics 항목 바로 아래에 추가:
```js
{
  name: "ahp",
  cwd: "/home/lab/knpu/ahp",
  script: "run.py",
  interpreter: "/home/lab/knpu/.venv/bin/python",
  watch: false,   // 파일 변경 시 재시작되면 접속 중인 웹소켓이 전부 끊긴다
  time: true
},
```
그 뒤 `pm2 start ecosystem.config.js --only ahp` (또는 전체 재기동) → `pm2 save`.

### nginx 사이트 설정 — `network.knpu.re.kr`을 그대로 복제
아래처럼 포트만 8010으로 바꾸고, **웹소켓 업그레이드 헤더와 긴 타임아웃을 반드시 유지**한다
(`/ws/console/*`, `/ws/respond/*`가 이게 없으면 즉시 끊긴다):
```nginx
server {
    listen 443 ssl http2;
    server_name ahp.knpu.re.kr;
    # ssl_certificate 등은 기존 network.knpu.re.kr 설정에서 그대로 복사

    location / {
        proxy_pass http://localhost:8010;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
        proxy_connect_timeout 86400;
    }
}
```
DNS에 `ahp.knpu.re.kr` A 레코드 추가 + `certbot`으로 인증서 발급도 필요.

### 확인
```bash
pm2 list | grep ahp        # online, watch=disabled
ss -lntp | grep :8010       # 리스닝 확인
curl -I https://ahp.knpu.re.kr/   # 302(로그인 리다이렉트)면 정상
```

---

## 13. 리스크

| 리스크 | 영향 | 대응 |
|---|---|---|
| 웹소켓 핸들러의 동기 DB 호출 | **치명** 접속자 전원 정지 | motor 사용, 리뷰 항목 고정 (4.1) |
| 웹소켓 인증 누락 | **치명** 누구나 관리자 채널 접근 | 엔드포인트 내 직접 검증 (5.3) |
| 현장 무선망 불안정 | **치명** 응답 유실 | 로컬 큐 + resync (7.5) |
| 방법론 미확정 착수 | **치명** 수집 데이터 재해석 불가 | 11절 선확정 |
| 무효화 범위 미정 | 높음 | 노드 uuid 저장 + 변경 분류표 (7.4) |
| 설문 중 배포로 세션 중단 | 높음 | `watch: false`, 세션 중 배포 금지 |
| ecosystem.config.js 누락 | 중간 | 배포 체크리스트 (3절) |
| 한 부모에 기준 과다 | 중간 | 설계 시점 경고 (7개 초과 = 21쌍) |
