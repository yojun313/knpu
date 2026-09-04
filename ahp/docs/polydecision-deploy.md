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
4. [ ] **DB 마이그레이션 실행** — 아래 "단계별 마이그레이션" 순서대로
5. [ ] `pm2 restart ahp` (`watch:false` 확인)
6. [ ] 스모크: `/` 302, 관리자 로그인 → 프로젝트 목록 → 설문지 화면 → 결과 화면 로드,
       기존 응답의 가중치·CR 값이 배포 전과 동일한지 1건 대조

---

## 단계별 마이그레이션

### 1단계 — 식별자 개명 `matrix_id → group_id`  *(코드: 완료 / 운영: 미실행)*

`matrix_id`→`group_id`, `surveys.matrices`→`surveys.groups`,
`respondents.revision_matrix_id`→`revision_group_id` 전면 개명.
`responses`/`submissions` 문서 내용은 **무변경**(바깥 키가 리터럴이 아니라 `parent_uuid` /
`"alt:<uuid>"` 값이라 그대로 `group_id` 값이 됨).

```bash
# repo 루트에서
PYTHONPATH=/home/wcchoi/knpu:/home/wcchoi/knpu/ahp \
  /home/wcchoi/knpu/.venv/bin/python ahp/scripts/migrate_matrix_to_group.py --dry-run   # 확인
PYTHONPATH=/home/wcchoi/knpu:/home/wcchoi/knpu/ahp \
  /home/wcchoi/knpu/.venv/bin/python ahp/scripts/migrate_matrix_to_group.py             # 실행
```

- 멱등: 이미 개명된 문서는 건너뛴다. 재실행 안전.
- 실행 후 스크립트가 `surveys.matrices` / `respondents.revision_matrix_id` 잔존 0을 검증하고,
  남아 있으면 non-zero 종료.
- 검증 dry-run 기준 대상: `surveys` 9건.
- **코드 배포와 이 마이그레이션은 함께** 나가야 한다(개명된 코드는 DB에 `groups`/`group_id`가
  있어야 동작). 프로덕션 서버는 단일 워커라 lockstep 부담은 `pm2 restart` 1회 수준.

### 2단계 — *(작성 예정)*

---

## 참고: 롤백

1단계까지만 반영한 상태에서 롤백이 필요하면 — 코드를 이전 커밋으로 되돌리고 `mongodump`
백업을 복원한다. (개명 마이그레이션의 역방향 스크립트는 만들지 않았다. 백업 복원이 정석.)
