"""내보내기 — Word 설문지, Excel 재현 패키지, CSV 원자료."""

import csv
import io
from urllib.parse import quote

from fastapi import APIRouter, Query, Request, Response

from app.db import projects_db
from app.routes.result_routes import (
    _get_project_checked,
    _canonical_survey_and_hierarchy,
    _gather_final_submissions,
)
from app.services.docx_export import build_survey_docx
from app.services.sheet_export import build_workbook, build_response_rows
from app.services.csv_schema import CSV_COLUMNS
from app.services.result_service import build_results

router = APIRouter()


def _download_headers(filename: str) -> dict:
    return {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}


def _nodes_by_uuid(hierarchy: dict) -> dict:
    """기준 노드 + 대안을 한 조회 경로로 합친다 — 대안 비교 행렬(is_alternative)의
    child_uuids는 대안 uuid라 기준 노드만으로는 이름을 못 찾는다."""
    out = {n["uuid"]: n for n in hierarchy["nodes"]}
    for a in hierarchy.get("alternatives", []):
        out[a["uuid"]] = a
    return out


@router.get("/api/export/{project_id}/survey.docx")
async def export_survey_docx(project_id: str, request: Request):
    project = await _get_project_checked(project_id, request)
    survey, hierarchy = await _canonical_survey_and_hierarchy(project_id)
    nodes_by_uuid = _nodes_by_uuid(hierarchy)

    buf = build_survey_docx(survey, nodes_by_uuid)
    return Response(
        content=buf.read(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=_download_headers(f"{project['title']}_설문지.docx"),
    )


@router.get("/api/export/{project_id}/package.xlsx")
async def export_package_xlsx(
    project_id: str, request: Request, collection_id: str | None = Query(None)
):
    project = await _get_project_checked(project_id, request)
    survey, hierarchy = await _canonical_survey_and_hierarchy(project_id)
    nodes_by_uuid = _nodes_by_uuid(hierarchy)
    submissions = await _gather_final_submissions(
        project_id, [collection_id] if collection_id else None
    )

    response_rows = build_response_rows(survey["matrices"], nodes_by_uuid, submissions)
    results = (
        build_results(
            hierarchy["nodes"],
            survey["matrices"],
            submissions,
            project.get("settings", {}),
        )
        if submissions
        else None
    )

    buf = build_workbook(
        project, hierarchy, survey, nodes_by_uuid, response_rows, results
    )
    return Response(
        content=buf.read(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=_download_headers(f"{project['title']}_재현패키지.xlsx"),
    )


@router.get("/api/export/{project_id}/import-template.csv")
async def export_import_template_csv(project_id: str, request: Request):
    """오프라인 반입용 빈 양식 — csv_schema.CSV_COLUMNS와 1:1로 맞춘 헤더에
    parent/item_a/item_b만 현재 설문지 기준으로 미리 채우고 respondent/value는
    빈 칸으로 남긴다. 반입(entry_routes.import_csv)이 기대하는 열 구조와
    반드시 같아야 하므로 그 열거 로직(부모별 쌍 i<j)을 그대로 따라간다."""
    project = await _get_project_checked(project_id, request)
    survey, hierarchy = await _canonical_survey_and_hierarchy(project_id)
    nodes_by_uuid = _nodes_by_uuid(hierarchy)

    rows = []
    for m in survey["matrices"]:
        child_uuids = m["child_uuids"]
        parent_name = nodes_by_uuid.get(m["parent_uuid"], {}).get("name", "")
        for i in range(len(child_uuids)):
            for j in range(i + 1, len(child_uuids)):
                a, b = child_uuids[i], child_uuids[j]
                rows.append(
                    [
                        "",
                        parent_name,
                        nodes_by_uuid.get(a, {}).get("name", a),
                        nodes_by_uuid.get(b, {}).get("name", b),
                        "",
                    ]
                )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_COLUMNS)
    writer.writerows(rows)

    return Response(
        content="﻿" + buf.getvalue(),
        media_type="text/csv",
        headers=_download_headers(f"{project['title']}_반입양식.csv"),
    )


@router.get("/api/export/{project_id}/responses.csv")
async def export_responses_csv(
    project_id: str, request: Request, collection_id: str | None = Query(None)
):
    project = await _get_project_checked(project_id, request)
    survey, hierarchy = await _canonical_survey_and_hierarchy(project_id)
    nodes_by_uuid = _nodes_by_uuid(hierarchy)
    submissions = await _gather_final_submissions(
        project_id, [collection_id] if collection_id else None
    )
    rows = build_response_rows(survey["matrices"], nodes_by_uuid, submissions)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_COLUMNS)
    writer.writerows(rows)

    return Response(
        content="﻿" + buf.getvalue(),  # BOM — 엑셀에서 한글 CSV 깨짐 방지
        media_type="text/csv",
        headers=_download_headers(f"{project['title']}_응답원자료.csv"),
    )
