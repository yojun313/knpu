import os
import socket
import warnings

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = int(os.getenv("MONGO_PORT", 27017))
MONGO_USER = os.getenv("MONGO_USER")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD")
MONGO_AUTH_DB = os.getenv("MONGO_AUTH_DB", "admin")

_tunnel = None


def get_client() -> MongoClient:
    global _tunnel
    hostname = socket.gethostname()
    is_server = "knpu" in hostname or "server" in hostname

    if is_server:
        return MongoClient(
            f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}"
            f"@localhost:{MONGO_PORT}/?authSource={MONGO_AUTH_DB}"
        )

    warnings.filterwarnings("ignore", module="paramiko")
    from sshtunnel import SSHTunnelForwarder

    _tunnel = SSHTunnelForwarder(
        (os.getenv("SSH_HOST"), int(os.getenv("SSH_PORT", 22))),
        ssh_username=os.getenv("SSH_USER"),
        ssh_pkey=os.getenv("SSH_KEY"),
        remote_bind_address=(MONGO_HOST, MONGO_PORT),
    )
    _tunnel.start()
    return MongoClient(
        f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}"
        f"@127.0.0.1:{_tunnel.local_bind_port}/?authSource={MONGO_AUTH_DB}"
    )
