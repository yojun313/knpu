"""PolyDecision 0단계 — `ahp` DB → `mcdm` DB 변환 복사 (1회, 멱등).

구 `ahp` DB는 **손대지 않는다**(롤백·이력용). 이 스크립트는 `ahp` 의 모든
컬렉션을 읽어 0단계 스키마로 변환한 뒤 새 `mcdm` DB 에 `_id` 기준 upsert 한다.
재실행하면 `mcdm` 문서가 최신 변환으로 덮어써진다(안전).

    PYTHONPATH=/home/wcchoi/knpu:/home/wcchoi/knpu/ahp \
        /home/wcchoi/knpu/.venv/bin/python ahp/scripts/migrate_ahp_to_mcdm.py [--dry-run]

변환 내용
--------
- surveys : `matrices` → `groups` (원소 `matrix_id` → `group_id`), 각 그룹에
  `kind:"pairwise"` · `method:"ahp"` · `scale`(프로젝트 settings.scale) 백필,
  `methods` 없으면 `{"criteria":{}, "alternatives":"ahp"}` 백필.
- respondents : `revision_matrix_id` → `revision_group_id`.
- hierarchies : `nodes[]` 에 `type:"benefit"` · `measure:"qualitative"` · `unit:None` 백필.
- 그 외(projects, collections, responses, submissions, results, imports) : 그대로 복사.
  `responses.answers` / `submissions.answers` 는 바깥 키가 이미 `group_id` 값(=parent_uuid /
  "alt:<uuid>")이라 변환 불필요.

인덱스는 앱 기동 시 `ensure_indexes()` 가 `mcdm` 에 새로 만든다 — 여기서 안 만든다.
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

from app.db import mongo_client  # noqa: E402  (연결/터널 설정 재사용)

# 기본: 운영 ahp → mcdm.
# 개발 시드는  MODE=0 AHP_SRC_DB=ahp_dev  로 실행 → ahp_dev → mcdm_dev.
SRC_NAME = os.getenv("AHP_SRC_DB", "ahp")
DST_NAME = os.getenv("AHP_DB_NAME") or (
    "mcdm_dev" if os.getenv("MODE", "1") == "0" else "mcdm"
)

COLLECTIONS = [
    "projects",
    "hierarchies",
    "surveys",
    "collections",
    "respondents",
    "responses",
    "submissions",
    "results",
    "imports",
]


def _xform_survey(doc: dict, scale_by_project: dict) -> dict:
    doc = dict(doc)
    groups = doc.pop("matrices", None)
    if groups is None:
        groups = doc.get("groups") or []
    scale = scale_by_project.get(doc.get("project_id"), 9)
    new_groups = []
    for m in groups:
        m = dict(m)
        if "matrix_id" in m:
            m["group_id"] = m.pop("matrix_id")
        m.setdefault("kind", "pairwise")
        m.setdefault("method", "ahp")
        m.setdefault("scale", scale)
        new_groups.append(m)
    doc["groups"] = new_groups
    if not isinstance(doc.get("methods"), dict) or "criteria" not in (
        doc.get("methods") or {}
    ):
        doc["methods"] = {"criteria": {}, "alternatives": "ahp"}
    return doc


def _xform_respondent(doc: dict) -> dict:
    doc = dict(doc)
    if "revision_matrix_id" in doc:
        doc["revision_group_id"] = doc.pop("revision_matrix_id")
    return doc


def _xform_hierarchy(doc: dict) -> dict:
    doc = dict(doc)
    nodes = []
    for n in doc.get("nodes") or []:
        n = dict(n)
        if n.get("type") not in ("benefit", "cost"):
            n["type"] = "benefit"
        if n.get("measure") not in ("qualitative", "quantitative"):
            n["measure"] = "qualitative"
        n.setdefault("unit", None)
        nodes.append(n)
    doc["nodes"] = nodes
    return doc


async def main() -> None:
    dry_run = "--dry-run" in sys.argv
    tag = "[dry-run] " if dry_run else ""

    if DST_NAME == SRC_NAME:
        sys.exit(f"대상 DB 이름이 원본과 같습니다({SRC_NAME}) — AHP_DB_NAME 확인")

    src = mongo_client[SRC_NAME]
    dst = mongo_client[DST_NAME]
    print(f"{tag}{SRC_NAME}  →  {DST_NAME}")

    scale_by_project = {
        p["_id"]: (p.get("settings") or {}).get("scale", 9)
        async for p in src["projects"].find({}, {"settings": 1})
    }

    xformers = {
        "surveys": lambda d: _xform_survey(d, scale_by_project),
        "respondents": _xform_respondent,
        "hierarchies": _xform_hierarchy,
    }

    total = 0
    for name in COLLECTIONS:
        xf = xformers.get(name)
        n = 0
        async for doc in src[name].find({}):
            out = xf(doc) if xf else doc
            if not dry_run:
                await dst[name].replace_one({"_id": out["_id"]}, out, upsert=True)
            n += 1
        total += n
        print(f"{tag}  {name:<13} {n}")
    print(f"{tag}total docs: {total}")

    if dry_run:
        print(f"{tag}no writes performed.")
        return

    # 잔존 검증 — mcdm 에 옛 필드가 남아 있으면 안 된다
    left_matrices = await dst["surveys"].count_documents({"matrices": {"$exists": True}})
    left_rev = await dst["respondents"].count_documents(
        {"revision_matrix_id": {"$exists": True}}
    )
    left_kind = await dst["surveys"].count_documents(
        {"groups": {"$elemMatch": {"kind": {"$exists": False}}}}
    )
    print(
        f"post-check(mcdm): surveys.matrices={left_matrices}, "
        f"revision_matrix_id={left_rev}, groups w/o kind={left_kind}"
    )
    if left_matrices or left_rev or left_kind:
        sys.exit("변환이 완전하지 않습니다 — 확인 필요")
    print("done. 이제 앱을 mcdm DB로 기동하면 된다 (AHP_DB_NAME 기본값=mcdm).")


if __name__ == "__main__":
    asyncio.run(main())
