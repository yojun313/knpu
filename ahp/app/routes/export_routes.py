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


@router.get("/api/export/{project_id}/survey.docx")
async def export_survey_docx(project_id: str, request: Request):
    project = await _get_project_checked(project_id, request)
    survey, hierarchy = await _canonical_survey_and_hierarchy(project_id)
    nodes_by_uuid = {n["uuid"]: n for n in hierarchy["nodes"]}

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
    nodes_by_uuid = {n["uuid"]: n for n in hierarchy["nodes"]}
    submissions = await _gather_final_submissions(project_id, collection_id)

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


@router.get("/api/export/{project_id}/responses.csv")
async def export_responses_csv(
    project_id: str, request: Request, collection_id: str | None = Query(None)
):
    project = await _get_project_checked(project_id, request)
    survey, hierarchy = await _canonical_survey_and_hierarchy(project_id)
    nodes_by_uuid = {n["uuid"]: n for n in hierarchy["nodes"]}
    submissions = await _gather_final_submissions(project_id, collection_id)
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
