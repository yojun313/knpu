import os
import socket
import warnings

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

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
is_server = "knpu" in hostname or "server" in hostname

if is_server:
    _mongo_uri = (
        f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}"
        f"@localhost:{MONGO_PORT}/?authSource={MONGO_AUTH_DB}"
    )
else:
    warnings.filterwarnings("ignore", module="paramiko")
    from sshtunnel import SSHTunnelForwarder

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

_client = AsyncIOMotorClient(_mongo_uri)

# dev/prod는 DB를 공유한다(system/db/__init__.py 참고).
ahp_db = _client["ahp"]

projects_db = ahp_db["projects"]
hierarchies_db = ahp_db["hierarchies"]
surveys_db = ahp_db["surveys"]
collections_db = ahp_db["collections"]
respondents_db = ahp_db["respondents"]
responses_db = ahp_db["responses"]
submissions_db = ahp_db["submissions"]
results_db = ahp_db["results"]
imports_db = ahp_db["imports"]


async def ensure_indexes():
    await responses_db.create_index(
        [("collection_id", 1), ("respondent_id", 1)], unique=True
    )
    await submissions_db.create_index(
        [("collection_id", 1), ("respondent_id", 1), ("round", 1)]
    )
    await respondents_db.create_index(
        [("collection_id", 1), ("code_hash", 1)],
        unique=True,
        partialFilterExpression={"code_hash": {"$type": "string"}},
    )
    await collections_db.create_index("access_token", unique=True, sparse=True)
    await hierarchies_db.create_index([("project_id", 1), ("version", 1)])
    await surveys_db.create_index([("project_id", 1), ("version", 1)])
