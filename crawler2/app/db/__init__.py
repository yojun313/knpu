from pymongo import MongoClient
from dotenv import load_dotenv
import os
import socket
import logging

from config import MODE

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

logger = logging.getLogger(__name__)

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
        set_keepalive=30,  # 30초마다 keepalive 패킷 전송 → idle timeout 방지
    )
    server.start()

    client = MongoClient(
        f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}"
        f"@127.0.0.1:{server.local_bind_port}/?authSource={MONGO_AUTH_DB}"
    )

manager_db_name = 'manager'
crawler_db_name = 'crawler'

crawler_db = client[crawler_db_name]
manager_db = client[manager_db_name]

user_db = manager_db['users']



def load_proxy_list():
    return client[crawler_db_name]['ip-list'].find_one({"_id": "proxy_list"})['list']

def checkStatus(dbUid):
    crawlDbList = client[crawler_db_name]['db-list']
    targetDB = crawlDbList.find_one({'uid': dbUid})
    if targetDB:
        return targetDB['status']
    return None

def get_userinfo(requester:str):
    try:
        userDBList = client['manager']['users']
        user = userDBList.find_one({'name': requester})
        if user is None:
            return False
        return {'Email': user['email'], 'PushOver': user['pushoverKey'], 'userUid': user['uid']}
    except Exception as e:
        logger.info(f"DB 유저 정보 가져오기 : {requester}, 에러: {e}")
        return False

def recordDB(dbUid, status):
    crawlDbList = client[crawler_db_name]['db-list']
    crawlDbList.update_one({'uid': dbUid}, {'$set': {'status': status}})