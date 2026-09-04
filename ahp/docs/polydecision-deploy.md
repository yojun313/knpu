# PolyDecision 확장 — 배포 시 필요한 작업 (누적)

> 0단계(추상화 도입) 리팩터링을 운영에 반영할 때 **코드 배포 외에** 해야 하는 작업을
> 단계별로 누적한다. 전체 설계는 `~/.claude/plans/ahp-compiled-shore.md` 참조.
>
> 공통 전제: 단일 워커(인메모리 WS 허브) → 배포는 **코드 반영 + `pm2 restart ahp`** 로
> 진행하며, 그 순간 접속 중이던 실시간 세션은 끊긴다. 실시간 세션 진행 중 배포 금지.

---

## 배포 체크리스트 (0단계 전체를 한 번에 반영할 때, 순서대로)

1. [ ] **백업**: `mongodump`  (ahp DB 전체)
2. [ ] 실시간 세션이 없는 시간대 확인
3. [ ] 코드 배포 (이 브랜치 머지/pull)
4. [ ] **DB 마이그레이션 1회 실행** — `ahp/scripts/migrate_polydecision_0dan.py`
       (0단계 전체를 담은 단일 멱등 스크립트, 아래 상세)
       ```bash
       PYTHONPATH=/home/wcchoi/knpu:/home/wcchoi/knpu/ahp \
         /home/wcchoi/knpu/.venv/bin/python ahp/scripts/migrate_polydecision_0dan.py --dry-run  # 확인
       PYTHONPATH=/home/wcchoi/knpu:/home/wcchoi/knpu/ahp \
         /home/wcchoi/knpu/.venv/bin/python ahp/scripts/migrate_polydecision_0dan.py            # 실행
       ```
5. [ ] `pm2 restart ahp` (`watch:false` 확인)
6. [ ] 스모크: `/` 302, 관리자 로그인 → 프로젝트 목록 → 설문지 화면 → 결과 화면 로드,
       기존 응답의 가중치·CR 값이 배포 전과 동일한지 1건 대조

> 마이그레이션은 **멱등**(재실행 안전)이고, 실행 끝에 잔존 검증(옛 필드 0, `groups.kind`
> 누락 0)을 자체 수행한다. 남아 있으면 non-zero 종료.

---

## 단계별 상세 (마이그레이션 스크립트가 각각 처리하는 것)

### 1단계 — 식별자 개명 `matrix_id → group_id`  *(코드: 완료 / 운영: 미실행)*

`surveys.matrices`→`surveys.groups`(원소 `matrix_id`→`group_id`),
`respondents.revision_matrix_id`→`revision_group_id`.
`responses`/`submissions` 문서 내용은 **무변경**(바깥 키가 리터럴이 아니라 `parent_uuid` /
`"alt:<uuid>"` 값이라 그대로 `group_id` 값이 됨).

- **코드 배포와 이 마이그레이션은 함께** 나가야 한다(개명된 코드는 DB에 `groups`/`group_id`가
  있어야 동작). 프로덕션 서버는 단일 워커라 lockstep 부담은 `pm2 restart` 1회 수준.
- dry-run 기준 대상: `surveys` 9건.

### 2단계 — `mcdm/` 공유 코어 + `methods/` 플러그인 scaffold  *(코드: 완료 / DB: 조치 없음)*

`app/services/mcdm/`(재수출 shim) + `app/services/methods/`(플러그인 골격) 순수 추가.
DB 변화 없음, wiring 없음. 검증: `ahp/tests/check_methods_ahp.py`.

### 3·4단계 — `generate_questions` + `surveys.methods` + 플러그인 dispatch  *(코드: 완료 / 운영: 미실행)*

- `surveys.groups[]` 각 원소에 **`kind:"pairwise"`** · **`method:"ahp"`** · **`scale`**(프로젝트 `settings.scale`) 백필.
- `surveys.methods` 없으면 **`{"criteria":{}, "alternatives":"ahp"}`** 백필. 이후
  `PUT /api/projects/{id}/survey` body `methods` 로 편집(버전 bump 없음), `resync` 시
  `generate_questions` 가 이 값으로 그룹을 다시 만든다.
- `hierarchies.nodes[]` 각 원소에 **`type:"benefit"`** · **`measure:"qualitative"`** ·
  **`unit:null`** 백필 (SAW/TOPSIS 등 랭킹 방법용, AHP는 무시).
- 백필이 없어도 코드는 `m.get("kind","pairwise")` / `get_method(None)`(→ AHP 폴백) 으로
  견디지만, 데이터 uniform 을 위해 마이그레이션에 포함.
- **4단계** — `build_results`·`respond_routes`·`entry_routes`·`collection_routes` 의 AHP
  직접 호출(`derive_weights`·`aggregate_*`·`worst_offending_pairs`)을 `METHODS[...]` 플러그인
  dispatch 로 전환. **동작·출력 무변경**(`build_results` 골든 바이트 동일, 라우트 헬퍼 패리티
  9건). DB 조치는 위와 동일(별도 없음). 유일한 미세 차이: what-if 리뷰 차트(`group-eval`)의
  **동점 항목 정렬 순서** — `reverse=True` → `-weight` 안정정렬로 바뀌어 가중치가 완전히
  같을 때만 순서가 다름(실제 고유벡터 값에선 발생하지 않음).
- dry-run 기준 대상: `surveys` 9건, `hierarchies` 22건.

---

## 참고: 롤백

코드를 이전 커밋으로 되돌리고 `mongodump` 백업을 복원한다. (역방향 스크립트는 만들지
않았다 — 백필 필드는 남아 있어도 옛 코드가 무시하므로 무해하지만, 개명은 되돌려야 하니
백업 복원이 정석.)
