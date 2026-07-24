from pymongo import MongoClient
from dotenv import load_dotenv
import os
import socket

load_dotenv()

SSH_HOST = os.getenv("SSH_HOST")
SSH_PORT = int(os.getenv("SSH_PORT", 22))
SSH_USER = os.getenv("SSH_USER")
SSH_KEY = os.getenv("SSH_KEY")

# MongoDB 설정
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
    import warnings

    warnings.filterwarnings("ignore", module="paramiko")
    from sshtunnel import SSHTunnelForwarder

    # 외부에서 실행 → SSH 터널 사용
    server = SSHTunnelForwarder(
        (SSH_HOST, SSH_PORT),
        ssh_username=SSH_USER,
        ssh_pkey=SSH_KEY,
        remote_bind_address=(MONGO_HOST, MONGO_PORT),
    )
    server.start()

    client = MongoClient(
        f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}"
        f"@127.0.0.1:{server.local_bind_port}/?authSource={MONGO_AUTH_DB}"
    )

manager_db_name = "manager"
crawler_db_name = "crawler"
homepage_db_name = "homepage"

manager_db = client[manager_db_name]
crawler_db = client[crawler_db_name]
homepage_db = client[homepage_db_name]

user_logs_col = manager_db["user-logs"]
bug_board_col = manager_db["bug-board"]
db_list_col = crawler_db["db-list"]
user_bugs_col = manager_db["user-bugs"]
homepage_users_col = homepage_db["users"]
