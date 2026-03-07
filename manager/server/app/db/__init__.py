from pymongo import MongoClient
from dotenv import load_dotenv
import os
import socket
from app.config import mode

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
is_server = ("knpu" in hostname or "server" in hostname)  # 서버 이름 기준으로 판단

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
        remote_bind_address=(MONGO_HOST, MONGO_PORT)
    )
    server.start()

    client = MongoClient(
        f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}"
        f"@127.0.0.1:{server.local_bind_port}/?authSource={MONGO_AUTH_DB}"
    )

if mode == 0:
    manager_db_name = 'manager_dev'
    crawler_db_name = 'crawler_dev'
else:    
    manager_db_name = 'manager'
    crawler_db_name = 'crawler'
    
manager_db = client[manager_db_name]
crawler_db = client[crawler_db_name]

crawlList_db = crawler_db["db-list"]
crawlLog_db = crawler_db["log-list"]

user_db = manager_db["users"]
user_logs_db = manager_db["user-logs"]
user_bugs_db = manager_db["user-bugs"]
version_board_db = manager_db["version-board"]
bug_board_db = manager_db["bug-board"]
free_board_db = manager_db["free-board"]
auth_db = manager_db["auth"]

crawldata_path = os.getenv('CRAWLDATA_PATH')

crawl_uid_list = [data['uid'] for data in crawlList_db.find({}, {"uid": 1, "_id": 0})]
log_uid_list = [data['uid'] for data in crawlLog_db.find({}, {"uid": 1, "_id": 0})]

for uid in log_uid_list:
    if uid not in crawl_uid_list:
        crawlLog_db.delete_one({"uid": uid})