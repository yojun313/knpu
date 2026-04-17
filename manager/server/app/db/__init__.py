from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
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

def sync_manager_databases(src_db_name='manager', target_db_name='manager_dev'):
    client.drop_database(target_db_name)
    
    src_db = client[src_db_name]
    target_db = client[target_db_name]
    
    for coll_name in src_db.list_collection_names():
        src_db[coll_name].aggregate([{"$out": {"db": target_db_name, "coll": coll_name}}])
        
        indexes = src_db[coll_name].index_information()
        for index_name, index_info in indexes.items():
            if index_name == "_id_":
                continue
            
            keys = index_info['key']
            options = {k: v for k, v in index_info.items() if k not in ['v', 'key', 'ns']}
            target_db[coll_name].create_index(keys, **options)

def migrate_kst(collection_name):
    coll = manager_db[collection_name]
    kst = ZoneInfo("Asia/Seoul")
    
    all_docs = coll.find()
    
    for doc in all_docs:
        dt = doc.get("datetime")
        if not dt or not isinstance(dt, datetime):
            continue
            
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
            
        dt_kst = dt.astimezone(kst)
        datetime_kst_str = dt_kst.strftime("%Y-%m-%d %H:%M:%S")
        
        coll.update_one(
            {"_id": doc["_id"]},
            {"$set": {"datetime_kst": datetime_kst_str}}
        )

