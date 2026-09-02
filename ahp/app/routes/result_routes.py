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
    respondents_db,
)
from app.services.result_service import build_results
from app.services.ahp_calc import sensitivity as calc_sensitivity
from app.services.demographics import resolve_for_export

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
    project_id: str,
    collection_ids: list[str] | None = None,
    round_by_collection: dict[str, int] | None = None,
) -> dict[str, dict]:
    """respondent_id -> 그 사람의 최종 제출 answers.

    collection_ids가 주어지면 그 회차들만, 아니면 프로젝트의 모든 회차를 합친다.
    round_by_collection에 특정 collection_id -> round가 있으면 그 회차는 "최신
    라운드"가 아니라 지정된 라운드의 제출만 쓴다(회차·라운드를 골라 조합해 보는
    결과 화면 기능, PLAN.md 13절). 지정이 없는 회차는 응답자별 최신 라운드를 쓰는
    기존 동작 그대로다."""
    survey_ids = [
        s["_id"] async for s in surveys_db.find({"project_id": project_id}, {"_id": 1})
    ]
    query = {"survey_id": {"$in": survey_ids}}
    if collection_ids:
        query = {"_id": {"$in": collection_ids}, "survey_id": {"$in": survey_ids}}
    resolved_ids = [c["_id"] async for c in collections_db.find(query, {"_id": 1})]
    if not resolved_ids:
        return {}

    round_by_collection = round_by_collection or {}
    latest_by_respondent: dict[str, dict] = {}
    async for sub in submissions_db.find({"collection_id": {"$in": resolved_ids}}):
        wanted_round = round_by_collection.get(sub["collection_id"])
        if wanted_round is not None and sub["round"] != wanted_round:
            continue
        rid = sub["respondent_id"]
        cur = latest_by_respondent.get(rid)
        if cur is None or sub["round"] > cur["round"]:
            latest_by_respondent[rid] = sub
    return {rid: sub["answers"] for rid, sub in latest_by_respondent.items()}


async def _gather_respondents(
    project_id: str, collection_ids: list[str] | None = None
) -> dict[str, dict]:
    """respondent_id -> 응답자 문서. 내보내기(인구통계)와 결과 필터가 공유한다."""
    survey_ids = [
        s["_id"] async for s in surveys_db.find({"project_id": project_id}, {"_id": 1})
    ]
    query = {"survey_id": {"$in": survey_ids}}
    if collection_ids:
        query = {"_id": {"$in": collection_ids}, "survey_id": {"$in": survey_ids}}
    cids = [c["_id"] async for c in collections_db.find(query, {"_id": 1})]
    if not cids:
        return {}
    return {
        r["_id"]: r
        async for r in respondents_db.find({"collection_id": {"$in": cids}})
    }


def _parse_demo_filters(raw: str | None) -> dict[str, set[str]]:
    """`f1:1,f1:3,f2:2` → {f1: {"1","3"}, f2: {"2"}} (필드 간 AND, 필드 내 OR)."""
    out: dict[str, set[str]] = {}
    for pair in (raw or "").split(","):
        fid, _, code = pair.partition(":")
        fid, code = fid.strip(), code.strip()
        if fid and code:
            out.setdefault(fid, set()).add(code)
    return out


def _respondent_matches(attributes: dict, filters: dict[str, set[str]]) -> bool:
    for fid, wanted in filters.items():
        v = (attributes or {}).get(fid)
        have = set(str(x) for x in v) if isinstance(v, (list, tuple)) else {str(v)}
        if have.isdisjoint(wanted):
            return False
    return True


def _demographics_summary(demographics: list[dict], respondents: list[dict]) -> list[dict]:
    out = []
    for f in demographics:
        entry = {"id": f["id"], "label": f["label"], "type": f["type"]}
        vals = [
            r.get("attributes", {}).get(f["id"])
            for r in respondents
            if r.get("attributes", {}).get(f["id"]) not in (None, "", [])
        ]
        if f["type"] in ("single", "multi"):
            counts: dict[str, int] = {}
            for v in vals:
                for code in v if isinstance(v, (list, tuple)) else [v]:
                    counts[str(code)] = counts.get(str(code), 0) + 1
            entry["distribution"] = [
                {"code": o["code"], "label": o["label"], "count": counts.get(o["code"], 0)}
                for o in f.get("options", [])
            ]
        elif f["type"] == "number":
            nums = [float(v) for v in vals]
            entry["stats"] = (
                {
                    "n": len(nums),
                    "min": min(nums),
                    "max": max(nums),
                    "mean": round(sum(nums) / len(nums), 2),
                }
                if nums
                else {"n": 0}
            )
        else:  # text
            entry["n"] = len(vals)
        out.append(entry)
    return out


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


def _parse_selection(
    collection_id: str | None, collection_ids: str | None, rounds: str | None
) -> tuple[list[str] | None, dict[str, int]]:
    """`collection_id`(단일, 하위호환) / `collection_ids`(콤마 구분 복수) /
    `rounds`(콤마 구분 "collection_id:round" 쌍)을 결과 조회용 선택 조건으로 푼다."""
    ids: list[str] | None = None
    if collection_ids:
        ids = [c for c in collection_ids.split(",") if c]
    elif collection_id:
        ids = [collection_id]

    round_map: dict[str, int] = {}
    if rounds:
        for pair in rounds.split(","):
            cid, _, rnd = pair.partition(":")
            if cid and rnd.isdigit():
                round_map[cid] = int(rnd)
    return ids, round_map


@router.get("/api/projects/{project_id}/collections/rounds")
async def get_collection_rounds(project_id: str, request: Request):
    """각 collection에 실제로 존재하는 라운드 목록 — 결과 화면에서 회차×라운드
    조합을 골라 종합해 볼 때 선택지로 쓴다."""
    await _get_project_checked(project_id, request)
    survey_ids = [
        s["_id"] async for s in surveys_db.find({"project_id": project_id}, {"_id": 1})
    ]
    colls = [
        c
        async for c in collections_db.find(
            {"survey_id": {"$in": survey_ids}}, {"_id": 1, "label": 1, "mode": 1}
        )
    ]
    out = []
    for c in colls:
        rounds = sorted(
            await submissions_db.distinct("round", {"collection_id": c["_id"]})
        )
        out.append(
            {
                "id": c["_id"],
                "label": c.get("label", ""),
                "mode": c.get("mode"),
                "rounds": rounds,
            }
        )
    return out


@router.get("/api/projects/{project_id}/results")
async def get_results(
    project_id: str,
    request: Request,
    collection_id: str | None = Query(None),
    collection_ids: str | None = Query(None),
    rounds: str | None = Query(None),
    demo_filters: str | None = Query(None),
):
    project = await _get_project_checked(project_id, request)
    survey, hierarchy = await _canonical_survey_and_hierarchy(project_id)
    ids, round_map = _parse_selection(collection_id, collection_ids, rounds)
    submissions = await _gather_final_submissions(project_id, ids, round_map)

    demographics = survey.get("demographics", [])
    respondents_by_id = (
        await _gather_respondents(project_id, ids) if demographics else {}
    )
    # 분포 요약은 인구통계 필터 적용 전(수집 범위 내 제출자) 기준 — 칩 선택지가 실제 값
    in_scope = [respondents_by_id[r] for r in submissions if r in respondents_by_id]
    demographics_summary = (
        _demographics_summary(demographics, in_scope) if demographics else []
    )
    demo_filter_map = _parse_demo_filters(demo_filters)
    if demo_filter_map:
        submissions = {
            rid: ans
            for rid, ans in submissions.items()
            if _respondent_matches(
                (respondents_by_id.get(rid) or {}).get("attributes", {}),
                demo_filter_map,
            )
        }

    # 대안(hierarchy.alternatives)은 기준 트리(hierarchy.nodes)와 별도의 평탄한
    # 목록이라(PLAN.md 5절 결정), build_results에 그대로 넘기면 node_parent 등
    # 트리 전제 로직이 깨진다(대안 항목엔 parent_id가 없다). 그래서 node_names만
    # 여기서 별도로 채운다 — 대안 순위(alternative_scores)의 키가 대안 uuid라
    # 이게 없으면 화면에 이름 대신 uuid가 그대로 노출된다.
    alt_names = {a["uuid"]: a["name"] for a in hierarchy.get("alternatives", [])}

    # matrix_id -> 부모 기준 이름. result.js가 이전엔 "matrix_id == parent_uuid"라는
    # 전제로 이 매핑을 클라이언트에서 유추했는데, 대안 비교 행렬은 matrix_id가
    # "alt:<leaf_uuid>" 형식이라(survey_service.generate_matrices) 그 전제가
    # 깨져 대안 섹션의 CR·합의도 행이 이름 대신 "alt:<uuid>"로 보였다.
    nodes_by_uuid = {n["uuid"]: n for n in hierarchy["nodes"]}
    matrix_parent_names = {
        m["matrix_id"]: (
            ("[대안] " if m.get("is_alternative") else "")
            + nodes_by_uuid.get(m["parent_uuid"], {}).get("name", "")
        )
        for m in survey["matrices"]
    }

    if not submissions:
        return {
            "respondent_count": 0,
            "global_weights": {},
            "local_weights": {},
            "per_respondent_cr": {},
            "consensus": {},
            "outliers": {},
            "node_names": {
                **{n["uuid"]: n["name"] for n in hierarchy["nodes"]},
                **alt_names,
            },
            "matrix_parent_names": matrix_parent_names,
            "demographics": demographics,
            "demographics_summary": demographics_summary,
            "message": (
                "선택한 인구통계 조건에 해당하는 응답이 없습니다"
                if demo_filter_map
                else "아직 제출된 응답이 없습니다"
            ),
        }

    results = build_results(
        hierarchy["nodes"], survey["matrices"], submissions, project.get("settings", {})
    )
    results["node_names"].update(alt_names)
    results["matrix_parent_names"] = matrix_parent_names
    results["demographics"] = demographics
    results["demographics_summary"] = demographics_summary
    return results


@router.get("/api/projects/{project_id}/results/sensitivity")
async def get_sensitivity(
    project_id: str,
    request: Request,
    target_node: str = Query(...),
    delta_pct: float = Query(...),
    collection_id: str | None = Query(None),
    collection_ids: str | None = Query(None),
    rounds: str | None = Query(None),
):
    project = await _get_project_checked(project_id, request)
    survey, hierarchy = await _canonical_survey_and_hierarchy(project_id)
    ids, round_map = _parse_selection(collection_id, collection_ids, rounds)
    submissions = await _gather_final_submissions(project_id, ids, round_map)
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
