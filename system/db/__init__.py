# system/db/__init__.py
"""KNPU 전 서비스가 공유하는 단일 MongoDB 연결 지점.

이전에는 manager/server, manager/{network,kemkim,statistics}, homepage/server, crawler,
admin, bot이 각자 MongoClient를 만들고 DB/컬렉션 이름을 흩어서 정의했다. 여기서 한 번만
연결하고, 아래 각 모듈이 이 파일의 핸들을 가져다 쓴다.

주의: 이 파일은 아직 "물리적으로" 기존 DB 구조(manager/homepage/crawler/discord/audit)를
그대로 가리킨다 — DB 자체를 systems/network/kemkim/statistics 등으로 재편하는 작업은
scripts/db/migrate.py로 데이터를 옮긴 뒤 이 파일에서 함께 전환한다(2단계 작업의 1단계).
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

manager_db_name = "manager_dev" if MODE == 0 else "manager"
crawler_db_name = "crawler_dev" if MODE == 0 else "crawler"

manager_db = client[manager_db_name]
crawler_db = client[crawler_db_name]
homepage_db = client["homepage"]
discord_db = client["discord"]
audit_db = client["audit"]

# ── 계정 (단일 진실 소스: homepage.users) ──
user_db = homepage_db["users"]
auth_codes_db = homepage_db["auth_codes"]
webauthn_credentials_db = homepage_db["webauthn_credentials"]
webauthn_challenges_db = homepage_db["webauthn_challenges"]
discord_link_requests_db = homepage_db["discord_link_requests"]

# ── homepage 콘텐츠 ──
members_db = homepage_db["members"]
news_db = homepage_db["news"]
papers_db = homepage_db["papers"]
gallery_db = homepage_db["gallery"]
popup_db = homepage_db["popups"]

# ── 세션 / 봇 설정 ──
sessions_db = manager_db["sessions"]
auth_config_db = manager_db["auth_config"]

# ── 로깅 ──
user_logs_db = manager_db["user-logs"]
user_bugs_db = manager_db["user-bugs"]
audit_logs_db = audit_db["logs"]
identities_db = audit_db["identities"]

# ── manager 게시판 ──
version_board_db = manager_db["version-board"]
bug_board_db = manager_db["bug-board"]
free_board_db = manager_db["free-board"]

# ── 서비스별 프로젝트 (아직 manager DB 안에 있음 — Phase 2에서 이관) ──
network_projects_db = manager_db["network-projects"]
network_folders_db = manager_db["network-folders"]
kemkim_projects_db = manager_db["kemkim-projects"]
kemkim_folders_db = manager_db["kemkim-folders"]
statistics_projects_db = manager_db["statistics-projects"]
statistics_folders_db = manager_db["statistics-folders"]

# ── 레거시 계정 (manager 데스크톱 앱이 과거에 쓰던 컬렉션). 마이그레이션 이전 로그의
# userUid가 이 컬렉션의 uid를 참조하므로 이름 매핑용으로 유지한다. ──
legacy_users_db = manager_db["users"]

# ── crawler ──
crawlList_db = crawler_db["db-list"]
crawlLog_db = crawler_db["log-list"]
crawlJobQueue_db = crawler_db["job-queue"]
crawlIpList_db = crawler_db["ip-list"]
crawlYoutubeApi_db = crawler_db["youtube_api"]

# ── 디스코드 알림 발행 큐 — 실제 전송은 system/bot(구 knpu/bot)이 폴링해서 처리한다 ──
discord_notifications_db = discord_db["notifications"]

crawldata_path = os.getenv("CRAWLDATA_PATH")


def get_user_names(uids: list[str]) -> dict[str, str]:
    """uid 목록 -> 표시용 이름. 계정 정보의 진짜 출처는 homepage.users이므로 조회만 한다."""
    if not uids:
        return {}
    docs = user_db.find({"uid": {"$in": list(set(uids))}}, {"uid": 1, "name": 1})
    return {d["uid"]: d.get("name", d["uid"]) for d in docs}
