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
    _gather_respondents,
)
from app.services.docx_export import build_survey_docx
from app.services.sheet_export import build_workbook, build_response_rows
from app.services.csv_schema import CSV_COLUMNS, RESPONDENT_COL, pair_column_label
from app.services.demographics import column_labels as demo_column_labels, resolve_for_export
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
    cids = [collection_id] if collection_id else None
    submissions = await _gather_final_submissions(project_id, cids)
    respondents_by_id = (
        await _gather_respondents(project_id, cids)
        if survey.get("demographics")
        else {}
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
        project, hierarchy, survey, nodes_by_uuid, response_rows, results,
        respondents_by_id=respondents_by_id,
    )
    return Response(
        content=buf.read(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=_download_headers(f"{project['title']}_재현패키지.xlsx"),
    )


@router.get("/api/export/{project_id}/import-template.csv")
async def export_import_template_csv(project_id: str, request: Request):
    """오프라인 반입용 빈 양식 — wide 형식. 열 배치는
    `[respondent] + [인구통계 항목들] + [Q1. 부모: A vs B, ...]`.
    응답자 한 명이 한 행이라 이름을 반복 입력하지 않는다. 비교쌍 열 순서(부모별 i<j
    전역 순서)는 entry_routes.import_csv의 슬롯 순서, print.js의 문항 번호와 같아야 한다."""
    project = await _get_project_checked(project_id, request)
    survey, hierarchy = await _canonical_survey_and_hierarchy(project_id)
    nodes_by_uuid = _nodes_by_uuid(hierarchy)

    header = [RESPONDENT_COL] + demo_column_labels(survey.get("demographics", []))
    n = 0
    for m in survey["matrices"]:
        child_uuids = m["child_uuids"]
        parent_name = nodes_by_uuid.get(m["parent_uuid"], {}).get("name", "")
        for i in range(len(child_uuids)):
            for j in range(i + 1, len(child_uuids)):
                a, b = child_uuids[i], child_uuids[j]
                n += 1
                header.append(
                    pair_column_label(
                        n,
                        parent_name,
                        nodes_by_uuid.get(a, {}).get("name", a),
                        nodes_by_uuid.get(b, {}).get("name", b),
                    )
                )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)  # 데이터 행 없음 — 응답자별로 한 줄씩 직접 추가

    return Response(
        content="﻿" + buf.getvalue(),
        media_type="text/csv",
        headers=_download_headers(f"{project['title']}_반입양식.csv"),
    )


@router.get("/api/export/{project_id}/demographics.csv")
async def export_demographics_csv(
    project_id: str, request: Request, collection_id: str | None = Query(None)
):
    """응답자별 인구통계 코딩 데이터 — respondent_id,label + 항목마다 코드/라벨 열."""
    project = await _get_project_checked(project_id, request)
    survey, _hierarchy = await _canonical_survey_and_hierarchy(project_id)
    demographics = survey.get("demographics", [])
    respondents = await _gather_respondents(
        project_id, [collection_id] if collection_id else None
    )

    columns = ["respondent_id", "label"]
    for f in demographics:
        columns.append(f"{f['label']}_code")
        columns.append(f"{f['label']}_label")

    rows = []
    for r in sorted(respondents.values(), key=lambda d: d.get("created_at") or 0):
        attrs = r.get("attributes", {})
        row = [r["_id"], r.get("label", "")]
        for f in demographics:
            resolved = resolve_for_export(f, attrs.get(f["id"]))
            row.append(resolved["code"])
            row.append(resolved["label"])
        rows.append(row)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(columns)
    writer.writerows(rows)
    return Response(
        content="﻿" + buf.getvalue(),
        media_type="text/csv",
        headers=_download_headers(f"{project['title']}_인구통계.csv"),
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
