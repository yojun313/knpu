import os
import socket
import warnings

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import OperationFailure
# 삭제 금지
from system.db import user_db, user_logs_db, get_user_names  # noqa: F401  (재수출)

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
    # offline 수집은 access_token을 명시적으로 None으로 저장한다. sparse 인덱스는
    # 필드가 "없는" 문서만 제외하고 값이 null인 문서는 색인하므로, offline collection이
    # 2개 이상이면 { access_token: null } 중복으로 E11000이 난다. 실제 토큰(문자열)에만
    # 유일성을 강제하는 partial 인덱스로 교체한다(respondents.code_hash와 동일 패턴).
    _existing = await collections_db.index_information()
    _spec = _existing.get("access_token_1")
    if _spec is not None and "partialFilterExpression" not in _spec:
        await collections_db.drop_index("access_token_1")  # 옛 sparse 정의 제거
    try:
        await collections_db.create_index(
            "access_token",
            unique=True,
            partialFilterExpression={"access_token": {"$type": "string"}},
        )
    except OperationFailure:
        pass  # 이미 동일 정의로 존재
    await hierarchies_db.create_index([("project_id", 1), ("version", 1)])
    await surveys_db.create_index([("project_id", 1), ("version", 1)])
