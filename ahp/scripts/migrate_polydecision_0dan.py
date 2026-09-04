"""PolyDecision 0단계 — 1회 스키마 마이그레이션 (멱등, 재실행 안전).

0단계 리팩터링을 운영에 반영할 때 코드 배포와 함께 딱 한 번 실행한다.
실행 전 `mongodump` 권고.

    PYTHONPATH=/home/wcchoi/knpu:/home/wcchoi/knpu/ahp \
        /home/wcchoi/knpu/.venv/bin/python ahp/scripts/migrate_polydecision_0dan.py [--dry-run]

하는 일
--------
1. 개명(A3): `surveys.matrices` → `surveys.groups` (원소 `matrix_id` → `group_id`),
   `respondents.revision_matrix_id` → `revision_group_id`.
   `responses.answers` / `submissions.answers` 는 무변경 — 바깥 키가 리터럴이 아니라
   `parent_uuid` / `"alt:<uuid>"` **값**이고 그 값이 그대로 `group_id` 값이 된다.
2. 백필: `surveys.groups[]` 각 원소에 `kind:"pairwise"`·`scale`(프로젝트 설정) 채움,
   `surveys.methods` 없으면 `{"criteria":{}, "alternatives":"ahp"}` 채움.
3. 백필: `hierarchies.nodes[]` 각 원소에 `type:"benefit"`·`measure:"qualitative"`·
   `unit:None` 채움 (랭킹 방법용, AHP는 무시).
"""

from __future__ import annotations

import asyncio
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_AHP_DIR = os.path.dirname(_HERE)
_REPO_ROOT = os.path.dirname(_AHP_DIR)
for _p in (_REPO_ROOT, _AHP_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.db import hierarchies_db, projects_db, respondents_db, surveys_db  # noqa: E402


async def _project_scale(project_id: str, cache: dict) -> int:
    if project_id not in cache:
        p = await projects_db.find_one({"_id": project_id}, {"settings": 1})
        cache[project_id] = ((p or {}).get("settings") or {}).get("scale", 9)
    return cache[project_id]


async def migrate_surveys(dry_run: bool) -> tuple[int, int]:
    scanned = touched = 0
    scale_cache: dict = {}
    async for doc in surveys_db.find({}):
        scanned += 1
        set_payload: dict = {}
        unset_payload: dict = {}

        groups = doc.get("groups")
        if groups is None and "matrices" in doc:  # 개명
            groups = doc["matrices"]
            unset_payload["matrices"] = ""
        groups = groups or []

        scale = await _project_scale(doc["project_id"], scale_cache)
        new_groups = []
        changed_groups = "matrices" in unset_payload
        for m in groups:
            m = dict(m)
            if "matrix_id" in m:
                m["group_id"] = m.pop("matrix_id")
                changed_groups = True
            if "kind" not in m:
                m["kind"] = "pairwise"
                changed_groups = True
            if "scale" not in m:
                m["scale"] = scale
                changed_groups = True
            new_groups.append(m)
        if changed_groups:
            set_payload["groups"] = new_groups

        if not isinstance(doc.get("methods"), dict) or "criteria" not in (
            doc.get("methods") or {}
        ):
            set_payload["methods"] = {"criteria": {}, "alternatives": "ahp"}

        if set_payload or unset_payload:
            touched += 1
            if not dry_run:
                op: dict = {}
                if set_payload:
                    op["$set"] = set_payload
                if unset_payload:
                    op["$unset"] = unset_payload
                await surveys_db.update_one({"_id": doc["_id"]}, op)
    return scanned, touched


async def migrate_respondents(dry_run: bool) -> int:
    touched = 0
    async for doc in respondents_db.find({"revision_matrix_id": {"$exists": True}}):
        touched += 1
        if not dry_run:
            await respondents_db.update_one(
                {"_id": doc["_id"]},
                {
                    "$set": {"revision_group_id": doc["revision_matrix_id"]},
                    "$unset": {"revision_matrix_id": ""},
                },
            )
    return touched


async def migrate_hierarchies(dry_run: bool) -> tuple[int, int]:
    scanned = touched = 0
    async for doc in hierarchies_db.find({}):
        scanned += 1
        nodes = doc.get("nodes") or []
        changed = False
        new_nodes = []
        for n in nodes:
            n = dict(n)
            if n.get("type") not in ("benefit", "cost"):
                n["type"] = "benefit"
                changed = True
            if n.get("measure") not in ("qualitative", "quantitative"):
                n["measure"] = "qualitative"
                changed = True
            if "unit" not in n:
                n["unit"] = None
                changed = True
            new_nodes.append(n)
        if changed:
            touched += 1
            if not dry_run:
                await hierarchies_db.update_one(
                    {"_id": doc["_id"]}, {"$set": {"nodes": new_nodes}}
                )
    return scanned, touched


async def main() -> None:
    dry_run = "--dry-run" in sys.argv
    tag = "[dry-run] " if dry_run else ""

    s_scanned, s_touched = await migrate_surveys(dry_run)
    print(f"{tag}surveys:     {s_scanned} scanned, {s_touched} updated")
    r_touched = await migrate_respondents(dry_run)
    print(f"{tag}respondents: {r_touched} renamed (revision_matrix_id→revision_group_id)")
    h_scanned, h_touched = await migrate_hierarchies(dry_run)
    print(f"{tag}hierarchies: {h_scanned} scanned, {h_touched} backfilled")

    if dry_run:
        print(f"{tag}no writes performed.")
        return

    leftover_surveys = await surveys_db.count_documents({"matrices": {"$exists": True}})
    leftover_resp = await respondents_db.count_documents(
        {"revision_matrix_id": {"$exists": True}}
    )
    missing_kind = await surveys_db.count_documents(
        {"groups": {"$elemMatch": {"kind": {"$exists": False}}}}
    )
    print(
        f"post-check: surveys.matrices leftover={leftover_surveys}, "
        f"respondents.revision_matrix_id leftover={leftover_resp}, "
        f"surveys w/o groups.kind={missing_kind}"
    )
    if leftover_surveys or leftover_resp:
        sys.exit("잔존 문서가 있습니다 — 확인 필요")
    print("done.")


if __name__ == "__main__":
    asyncio.run(main())
