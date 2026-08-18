"""분석 결과 — 여러 collection(오프라인/온라인/실시간)의 응답을 프로젝트 단위로
합쳐서 분석한다(PLAN.md 1절: "같은 설문지로 받은 오프라인/온라인 응답을 한
분석에 합칠 수 있다"). ?collection_id=로 특정 회차만 드릴다운할 수 있다.
"""

from fastapi import APIRouter, HTTPException, Query, Request

from app.auth import current_uid, is_admin
from app.db import (
    projects_db,
    surveys_db,
    hierarchies_db,
    collections_db,
    submissions_db,
)
from app.services.result_service import build_results
from app.services.ahp_calc import sensitivity as calc_sensitivity

router = APIRouter()


async def _get_project_checked(project_id: str, request: Request) -> dict:
    doc = await projects_db.find_one({"_id": project_id})
    if not doc:
        raise HTTPException(404, "프로젝트를 찾을 수 없습니다")
    uid = current_uid(request)
    if doc.get("owner_uid") != uid and not is_admin(request):
        raise HTTPException(403, "이 프로젝트에 접근할 권한이 없습니다")
    return doc


async def _gather_final_submissions(
    project_id: str, collection_id: str | None
) -> dict[str, dict]:
    """respondent_id -> 그 사람의 최종(가장 높은 round) 제출 answers.
    collection_id가 주어지면 그 회차만, 아니면 프로젝트의 모든 회차를 합친다."""
    survey_ids = [
        s["_id"] async for s in surveys_db.find({"project_id": project_id}, {"_id": 1})
    ]
    query = {"survey_id": {"$in": survey_ids}}
    if collection_id:
        query = {"_id": collection_id, "survey_id": {"$in": survey_ids}}
    collection_ids = [c["_id"] async for c in collections_db.find(query, {"_id": 1})]
    if not collection_ids:
        return {}

    latest_by_respondent: dict[str, dict] = {}
    async for sub in submissions_db.find({"collection_id": {"$in": collection_ids}}):
        rid = sub["respondent_id"]
        cur = latest_by_respondent.get(rid)
        if cur is None or sub["round"] > cur["round"]:
            latest_by_respondent[rid] = sub
    return {rid: sub["answers"] for rid, sub in latest_by_respondent.items()}


async def _canonical_survey_and_hierarchy(project_id: str):
    survey = await surveys_db.find_one(
        {"project_id": project_id}, sort=[("version", -1)]
    )
    if not survey:
        raise HTTPException(404, "설문지가 없습니다")
    hierarchy = await hierarchies_db.find_one(
        {"project_id": project_id, "version": survey["hierarchy_version"]}
    )
    if not hierarchy:
        raise HTTPException(404, "계층을 찾을 수 없습니다")
    return survey, hierarchy


@router.get("/api/projects/{project_id}/results")
async def get_results(
    project_id: str, request: Request, collection_id: str | None = Query(None)
):
    project = await _get_project_checked(project_id, request)
    survey, hierarchy = await _canonical_survey_and_hierarchy(project_id)
    submissions = await _gather_final_submissions(project_id, collection_id)

    if not submissions:
        return {
            "respondent_count": 0,
            "global_weights": {},
            "local_weights": {},
            "per_respondent_cr": {},
            "consensus": {},
            "outliers": {},
            "node_names": {n["uuid"]: n["name"] for n in hierarchy["nodes"]},
            "message": "아직 제출된 응답이 없습니다",
        }

    return build_results(
        hierarchy["nodes"], survey["matrices"], submissions, project.get("settings", {})
    )


@router.get("/api/projects/{project_id}/results/sensitivity")
async def get_sensitivity(
    project_id: str,
    request: Request,
    target_node: str = Query(...),
    delta_pct: float = Query(...),
    collection_id: str | None = Query(None),
):
    project = await _get_project_checked(project_id, request)
    survey, hierarchy = await _canonical_survey_and_hierarchy(project_id)
    submissions = await _gather_final_submissions(project_id, collection_id)
    if not submissions:
        raise HTTPException(400, "응답이 없어 민감도 분석을 할 수 없습니다")

    results = build_results(
        hierarchy["nodes"], survey["matrices"], submissions, project.get("settings", {})
    )
    node_parent = {n["uuid"]: n["parent_id"] for n in hierarchy["nodes"]}
    matrix_of_parent = {m["parent_uuid"]: m["matrix_id"] for m in survey["matrices"]}

    if target_node not in node_parent:
        raise HTTPException(404, "해당 노드를 찾을 수 없습니다")

    new_weights = calc_sensitivity(
        results["local_weights"], matrix_of_parent, node_parent, target_node, delta_pct
    )
    return {"original": results["global_weights"], "adjusted": new_weights}
