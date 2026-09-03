import os
import socket
import warnings

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

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

# dev(MODE=0)도 아래 DB를 그대로 쓴다. 예전엔 MODE=0일 때 "_dev" 접미사를 붙였는데
# 그 DB들이 실제로 만들어진 적이 없어서, dev 사이트는 논문/구성원 같은 콘텐츠가 통째로
# 비어 보였고 systems_dev에 계정이 없으니 dev-* 서브도메인은 세션 검증에 실패해
# 로그인 페이지로 무한히 되돌아갔다.
systems_db = client["systems"]
manager_db = client["manager"]
crawler_db = client["crawler"]
homepage_db = client["homepage"]
network_db = client["network"]
kemkim_db = client["kemkim"]
statistics_db = client["statistics"]

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
    if not uids:
        return {}
    docs = user_db.find({"uid": {"$in": list(set(uids))}}, {"uid": 1, "name": 1})
    return {d["uid"]: d.get("name", d["uid"]) for d in docs}
