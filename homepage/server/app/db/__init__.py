"""system.db가 관리하는 단일 MongoDB 연결의 핸들을 재노출한다 — 예전에는 이 서비스가
자체 MongoClient(+SSH 터널)를 별도로 만들어서 프로세스마다 연결이 중복됐다.

이름은 이 서비스의 기존 호출부(app.auth.*, app.routes.*)와 맞추기 위해 그대로 유지한다
(예: users_db, discord_link_col — system.db 쪽 이름과 다를 수 있음)."""

from system.db import (
    user_db as users_db,
    members_db,
    news_db,
    papers_db,
    gallery_db,
    popup_db,
    auth_codes_db,
    discord_link_requests_db as discord_link_col,
    legacy_users_db as manager_users_db,
    user_logs_db,
    discord_notifications_db,
    webauthn_credentials_db,
    webauthn_challenges_db,
)

__all__ = [
    "users_db",
    "members_db",
    "news_db",
    "papers_db",
    "gallery_db",
    "popup_db",
    "auth_codes_db",
    "discord_link_col",
    "manager_users_db",
    "user_logs_db",
    "discord_notifications_db",
    "webauthn_credentials_db",
    "webauthn_challenges_db",
]
