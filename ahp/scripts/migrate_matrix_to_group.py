"""1회 스키마 개명 마이그레이션 — PolyDecision 0단계(A3).

`matrix_id` → `group_id`, `surveys.matrices` → `surveys.groups`,
`respondents.revision_matrix_id` → `revision_group_id`.

`responses.answers` / `submissions.answers` 는 건드리지 않는다 — 바깥 키가 리터럴
`"matrix_id"` 가 아니라 `parent_uuid` / `"alt:<uuid>"` **값**이고, 그 값이 그대로
`group_id` 값이 되기 때문이다.

멱등: 이미 개명된 문서는 건너뛴다. 여러 번 실행해도 안전하다.
실행 전 `mongodump` 권고.

    PYTHONPATH=/home/wcchoi/knpu:/home/wcchoi/knpu/ahp \
        /home/wcchoi/knpu/.venv/bin/python ahp/scripts/migrate_matrix_to_group.py [--dry-run]
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

from app.db import surveys_db, respondents_db  # noqa: E402


def _rename_survey_doc(doc: dict) -> dict | None:
    """개명이 필요하면 $set/$unset 페이로드를, 아니면 None을 돌려준다."""
    if "matrices" not in doc:
        return None  # 이미 개명됨(또는 matrices 없음)
    old = doc.get("matrices") or []
    new_groups = []
    for m in old:
        m = dict(m)
        if "matrix_id" in m:
            m["group_id"] = m.pop("matrix_id")
        new_groups.append(m)
    return {"$set": {"groups": new_groups}, "$unset": {"matrices": ""}}


async def migrate_surveys(dry_run: bool) -> tuple[int, int]:
    seen = changed = 0
    async for doc in surveys_db.find({}):
        seen += 1
        payload = _rename_survey_doc(doc)
        if payload is None:
            continue
        changed += 1
        if not dry_run:
            await surveys_db.update_one({"_id": doc["_id"]}, payload)
    return seen, changed


async def migrate_respondents(dry_run: bool) -> tuple[int, int]:
    seen = changed = 0
    async for doc in respondents_db.find({"revision_matrix_id": {"$exists": True}}):
        seen += 1
        changed += 1
        if not dry_run:
            await respondents_db.update_one(
                {"_id": doc["_id"]},
                {
                    "$set": {"revision_group_id": doc["revision_matrix_id"]},
                    "$unset": {"revision_matrix_id": ""},
                },
            )
    return seen, changed


async def main() -> None:
    dry_run = "--dry-run" in sys.argv
    tag = "[dry-run] " if dry_run else ""

    s_seen, s_changed = await migrate_surveys(dry_run)
    print(f"{tag}surveys: {s_seen} scanned, {s_changed} renamed (matrices→groups)")

    r_seen, r_changed = await migrate_respondents(dry_run)
    print(
        f"{tag}respondents: {r_changed} renamed "
        f"(revision_matrix_id→revision_group_id)"
    )

    if dry_run:
        print(f"{tag}no writes performed.")
        return

    # 잔존 검증 (개명 후 옛 필드가 남아 있으면 안 된다)
    leftover_surveys = await surveys_db.count_documents({"matrices": {"$exists": True}})
    leftover_resp = await respondents_db.count_documents(
        {"revision_matrix_id": {"$exists": True}}
    )
    print(
        f"post-check: surveys.matrices leftover={leftover_surveys}, "
        f"respondents.revision_matrix_id leftover={leftover_resp}"
    )
    if leftover_surveys or leftover_resp:
        sys.exit("잔존 문서가 있습니다 — 확인 필요")
    print("done.")


if __name__ == "__main__":
    asyncio.run(main())
