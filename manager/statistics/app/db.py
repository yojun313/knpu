# app/db.py
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

statistics_projects_db = manager_db["statistics-projects"]
statistics_folders_db = manager_db["statistics-folders"]
user_logs_db = manager_db["user-logs"]
homepage_db = client["homepage"]
user_db = homepage_db["users"]


def get_user_names(uids: list[str]) -> dict[str, str]:
    if not uids:
        return {}
    docs = user_db.find({"uid": {"$in": list(set(uids))}}, {"uid": 1, "name": 1})
    return {d["uid"]: d.get("name", d["uid"]) for d in docs}
