# app/db.py
"""system.db가 관리하는 단일 MongoDB 연결의 핸들을 재노출한다 — 예전에는 이 서비스가
자체 MongoClient(+SSH 터널)를 별도로 만들어서 프로세스마다 연결이 중복됐다."""

from system.db import (
    user_db,
    user_logs_db,
    kemkim_folders_db,
    kemkim_projects_db,
    get_user_names,
)

__all__ = [
    "user_db",
    "user_logs_db",
    "kemkim_folders_db",
    "kemkim_projects_db",
    "get_user_names",
]
