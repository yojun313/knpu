# app/db.py
"""crawler/manager/server와 같은 MongoDB(manager DB)에 연결한다.
계정 인증은 knpu.re.kr 중앙 로그인이 전담하므로, 여기서는 프로젝트 데이터만 다룬다."""

import os
import socket

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MODE = int(os.getenv("MODE", 1))

MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = int(os.getenv("MONGO_PORT", 27017))
MONGO_USER = os.getenv("MONGO_USER")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD")
MONGO_AUTH_DB = os.getenv("MONGO_AUTH_DB", "admin")

hostname = socket.gethostname()
is_server = "knpu" in hostname or "server" in hostname

if is_server:
    client = MongoClient(
        f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}"
        f"@localhost:{MONGO_PORT}/?authSource={MONGO_AUTH_DB}"
    )
else:
    import warnings

    warnings.filterwarnings("ignore", module="paramiko")
    from sshtunnel import SSHTunnelForwarder

    server = SSHTunnelForwarder(
        (os.getenv("SSH_HOST"), int(os.getenv("SSH_PORT", 22))),
        ssh_username=os.getenv("SSH_USER"),
        ssh_pkey=os.getenv("SSH_KEY"),
        remote_bind_address=(MONGO_HOST, MONGO_PORT),
    )
    server.start()
    client = MongoClient(
        f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}"
        f"@127.0.0.1:{server.local_bind_port}/?authSource={MONGO_AUTH_DB}"
    )

manager_db_name = "manager_dev" if MODE == 0 else "manager"
manager_db = client[manager_db_name]

network_projects_db = manager_db["network-projects"]
