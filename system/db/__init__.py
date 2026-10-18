import os

from .connection import client, get_async_client, close_connections
from .names import DATABASE_NAMES, database_name

systems_db = client[DATABASE_NAMES["systems"]]
manager_db = client[DATABASE_NAMES["manager"]]
crawler_db = client[DATABASE_NAMES["crawler"]]
homepage_db = client[DATABASE_NAMES["homepage"]]
network_db = client[DATABASE_NAMES["network"]]
kemkim_db = client[DATABASE_NAMES["kemkim"]]
statistics_db = client[DATABASE_NAMES["statistics"]]
whisper_db = client[DATABASE_NAMES["whisper"]]
admin_db = client[DATABASE_NAMES["admin"]]

user_db = systems_db["users"]
auth_codes_db = systems_db["auth-codes"]
webauthn_credentials_db = systems_db["webauthn-credentials"]
webauthn_challenges_db = systems_db["webauthn-challenges"]
discord_link_requests_db = systems_db["discord-link-requests"]

# ── homepage 콘텐츠 ──
members_db = homepage_db["members"]
news_db = homepage_db["news"]
papers_db = homepage_db["papers"]
gallery_db = homepage_db["gallery"]
popup_db = homepage_db["popups"]
admission_faq_db = homepage_db["admission-faq"]
admission_faq_categories_db = homepage_db["admission-faq-categories"]

# ── 세션 / 봇 설정 ──
sessions_db = systems_db["sessions"]
auth_config_db = systems_db["bot-config"]

# ── 로깅 ──
user_logs_db = systems_db["user-logs"]
user_bugs_db = systems_db["user-bugs"]
identities_db = systems_db["identities"]
analysis_jobs_db = systems_db["analysis_jobs"]
llm_activity_db = systems_db["llm_activity"]
llm_user_settings_db = systems_db["llm_user_settings"]
llm_user_usage_db = systems_db["llm_user_usage"]
admin_settings_db = admin_db["settings"]
whisper_notes_db = whisper_db["notes"]

# ── 웹 BOARD와 매니저 앱이 공유하는 게시판 ──
version_board_db = manager_db["version-board"]
bug_board_db = manager_db["bug-board"]
free_board_db = manager_db["free-board"]
suggestion_board_db = manager_db["suggestion-board"]

# ── 서비스별 프로젝트 ──
network_projects_db = network_db["projects"]
network_folders_db = network_db["folders"]
network_ai_jobs_db = network_db["ai-jobs"]
kemkim_projects_db = kemkim_db["projects"]
kemkim_folders_db = kemkim_db["folders"]
statistics_projects_db = statistics_db["projects"]
statistics_folders_db = statistics_db["folders"]

legacy_users_db = systems_db["legacy-users"]

# ── crawler ──
crawlList_db = crawler_db["db-list"]
crawlLog_db = crawler_db["log-list"]
crawlJobQueue_db = crawler_db["job-queue"]
crawlIpList_db = crawler_db["ip-list"]
crawlYoutubeApi_db = crawler_db["youtube-api"]

# ── 디스코드 알림 발행 큐 —
discord_notifications_db = systems_db["discord-notifications"]

crawldata_path = os.getenv("CRAWLDATA_PATH")


def get_user_names(uids: list[str]) -> dict[str, str]:
    if not uids:
        return {}
    docs = user_db.find({"uid": {"$in": list(set(uids))}}, {"uid": 1, "name": 1})
    return {d["uid"]: d.get("name", d["uid"]) for d in docs}
