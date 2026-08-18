# system/db/__init__.py
"""KNPU 전 서비스가 공유하는 단일 MongoDB 연결 지점.

이전에는 manager/server, manager/{network,kemkim,statistics}, homepage/server, crawler,
admin, bot이 각자 MongoClient를 만들고 DB/컬렉션 이름을 흩어서 정의했다. 여기서 한 번만
연결하고, 아래 각 모듈이 이 파일의 핸들을 가져다 쓴다.

DB 구조 (scripts/db/migrate.py로 이관 완료, scripts/db/verify.py로 검증됨):
- systems     : 계정/세션/인증코드/로그/감사로그/디스코드 알림 큐 등 전 서비스 공통 데이터
- homepage    : 홈페이지 콘텐츠(members/news/papers/gallery/popups)
- network / kemkim / statistics : 각 서비스의 projects/folders
- crawler     : 크롤러 데이터 (db-list/log-list/job-queue/ip-list/youtube-api)
- manager     : 매니저 게시판(version-board/bug-board/free-board)만 남음

기존 manager/homepage/discord/audit DB는 며칠간 그대로 두고(구 코드가 참조할 일이 없어지면)
수동으로 정리한다 — 이 파일에서는 더 이상 참조하지 않는다.
"""

import os
import socket
import warnings

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MODE = int(os.getenv("MODE", 1))

SSH_HOST = os.getenv("SSH_HOST")
SSH_PORT = int(os.getenv("SSH_PORT", 22))
SSH_USER = os.getenv("SSH_USER")
SSH_KEY = os.getenv("SSH_KEY")

MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = int(os.getenv("MONGO_PORT", 27017))
MONGO_USER = os.getenv("MONGO_USER")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD")
MONGO_AUTH_DB = os.getenv("MONGO_AUTH_DB", "admin")

hostname = socket.gethostname()
is_server = "knpu" in hostname or "server" in hostname  # 서버 이름 기준으로 판단

if is_server:
    # 서버 내부에서 실행 → 로컬 MongoDB 바로 사용
    client = MongoClient(
        f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}"
        f"@localhost:{MONGO_PORT}/?authSource={MONGO_AUTH_DB}"
    )
else:
    warnings.filterwarnings("ignore", module="paramiko")
    from sshtunnel import SSHTunnelForwarder

    # 외부에서 실행 → SSH 터널 사용
    _tunnel = SSHTunnelForwarder(
        (SSH_HOST, SSH_PORT),
        ssh_username=SSH_USER,
        ssh_pkey=SSH_KEY,
        remote_bind_address=(MONGO_HOST, MONGO_PORT),
    )
    _tunnel.start()

    client = MongoClient(
        f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}"
        f"@127.0.0.1:{_tunnel.local_bind_port}/?authSource={MONGO_AUTH_DB}"
    )

systems_db_name = "systems_dev" if MODE == 0 else "systems"
manager_db_name = "manager_dev" if MODE == 0 else "manager"
crawler_db_name = "crawler_dev" if MODE == 0 else "crawler"
network_db_name = "network_dev" if MODE == 0 else "network"
kemkim_db_name = "kemkim_dev" if MODE == 0 else "kemkim"
statistics_db_name = "statistics_dev" if MODE == 0 else "statistics"
homepage_db_name = "homepage_dev" if MODE == 0 else "homepage"

systems_db = client[systems_db_name]
manager_db = client[manager_db_name]
crawler_db = client[crawler_db_name]
homepage_db = client[homepage_db_name]
network_db = client[network_db_name]
kemkim_db = client[kemkim_db_name]
statistics_db = client[statistics_db_name]

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

# ── 세션 / 봇 설정 ──
sessions_db = systems_db["sessions"]
auth_config_db = systems_db["bot-config"]

# ── 로깅 ──
user_logs_db = systems_db["user-logs"]
user_bugs_db = systems_db["user-bugs"]
identities_db = systems_db["identities"]

# ── manager 게시판 (매니저 앱 전용으로 남은 유일한 데이터) ──
version_board_db = manager_db["version-board"]
bug_board_db = manager_db["bug-board"]
free_board_db = manager_db["free-board"]

# ── 서비스별 프로젝트 ──
network_projects_db = network_db["projects"]
network_folders_db = network_db["folders"]
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
    """uid 목록 -> 표시용 이름. 계정 정보의 진짜 출처는 systems.users이므로 조회만 한다."""
    if not uids:
        return {}
    docs = user_db.find({"uid": {"$in": list(set(uids))}}, {"uid": 1, "name": 1})
    return {d["uid"]: d.get("name", d["uid"]) for d in docs}
