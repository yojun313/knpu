"""system.db의 단일 MongoClient를 재사용한다 — 예전에는 이 서비스가 자체
MongoClient(+SSH 터널)를 별도로 만들어서 프로세스마다 연결이 중복됐다.

이 대시보드는 원래도 자신의 실행 모드와 무관하게 항상 운영(prod) DB만 봤다 — 그 동작을
그대로 보존해 systems/crawler/homepage 운영 DB 이름을 고정해서 가져온다."""

from system.db import client

crawler_db_name = "crawler"
homepage_db_name = "homepage"

systems_db = client["systems"]
crawler_db = client[crawler_db_name]
homepage_db = client[homepage_db_name]
manager_db = client["manager"]  # 게시판(bug-board 등)은 여전히 manager DB에 남아있다

user_logs_col = systems_db["user-logs"]
bug_board_col = manager_db["bug-board"]
db_list_col = crawler_db["db-list"]
crawler_log_col = crawler_db["log-list"]
user_bugs_col = systems_db["user-bugs"]
homepage_users_col = systems_db["users"]
audit_logs_col = systems_db["audit-logs"]

# 매니저 데스크톱 앱이 예전에 쓰던 레거시 계정 컬렉션. 지금은 systems.users가 단일
# 진실 소스지만, 마이그레이션 이전에 쌓인 user-logs/user-bugs의 userUid는 이 컬렉션의
# uid를 참조하고 있어 이름 매핑에 필요하다.
manager_users_col = systems_db["legacy-users"]

# uid→이름 매핑을 한 번 본 것은 영구 보관한다 — 계정이 삭제되거나 재가입으로 uid가
# 바뀌어도 과거 로그가 계속 이름으로 표시되도록 하기 위함 (get_user_mapping 참고).
identity_history_col = systems_db["identities"]

# 디스코드 알림 발행 큐 — 실제 전송은 디스코드 봇(system/bot/cogs/cog_notifications.py)이
# 이 컬렉션을 폴링해서 처리한다 (app/libs/discord_notify.py 참고).
discord_notifications_col = systems_db["discord-notifications"]

# admin 대시보드 자체 설정(사이드바 메뉴 순서 등) — 로그인한 기기/브라우저와 무관하게
# 유지되도록 localStorage가 아니라 서버 DB에 저장한다. (다른 서비스와 무관한 전용 DB)
admin_settings_col = client["admin"]["settings"]
