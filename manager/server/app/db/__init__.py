"""system.db가 관리하는 단일 MongoDB 연결의 핸들을 재노출한다 — 예전에는 이 서비스가
자체 MongoClient(+SSH 터널)를 별도로 만들어서 프로세스마다 연결이 중복됐다.

`client`와 `manager_db`는 app/db/sync.py가 `from . import client, manager_db`로 그대로
가져다 쓰므로 이름을 유지한다 (그 파일 자체는 "BE CAREFUL — Do Not Modify" 경고가 있어
손대지 않았다)."""

from system.db import (
    client,
    manager_db,
    crawler_db,
    homepage_db,
    user_db,
    user_logs_db,
    user_bugs_db,
    version_board_db,
    bug_board_db,
    free_board_db,
    discord_notifications_db,
)

__all__ = [
    "client",
    "manager_db",
    "crawler_db",
    "homepage_db",
    "user_db",
    "user_logs_db",
    "user_bugs_db",
    "version_board_db",
    "bug_board_db",
    "free_board_db",
    "discord_notifications_db",
]
