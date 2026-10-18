import os
import socket
import warnings
import atexit
import threading

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
    _mongo_uri = (
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

    _mongo_uri = (
        f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}"
        f"@127.0.0.1:{_tunnel.local_bind_port}/?authSource={MONGO_AUTH_DB}"
    )

client = MongoClient(_mongo_uri)
_async_clients = {}
_async_client_lock = threading.Lock()


def get_async_client(**options):
    """Get a shared Motor client using the common connection and SSH tunnel.

    Drivers retain their native synchronous/asynchronous interfaces. Motor is
    loaded only when an asynchronous consumer requests it.
    """
    key = tuple(sorted(options.items()))
    with _async_client_lock:
        if key not in _async_clients:
            from motor.motor_asyncio import AsyncIOMotorClient

            _async_clients[key] = AsyncIOMotorClient(_mongo_uri, **options)
        return _async_clients[key]


def close_connections():
    """Close drivers before stopping the shared SSH tunnel at process exit."""
    try:
        with _async_client_lock:
            clients = list(_async_clients.values())
            _async_clients.clear()
        for async_client in clients:
            async_client.close()
    finally:
        try:
            client.close()
        finally:
            if not is_server:
                _tunnel.stop()


atexit.register(close_connections)
