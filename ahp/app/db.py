"""AHP 전용 MongoDB 연결.

system/db는 동기 pymongo다. 워커가 1개인 실시간 웹소켓 서버에서 동기 드라이버를
쓰면 한 번의 쿼리가 이벤트 루프를 막아 접속자 전원이 함께 멈춘다(PLAN.md 7.1 참고).
그래서 AHP 데이터(ahp DB)는 motor(async)로 별도 연결하고, 계정 조회처럼 HTTP
요청 경로에서만 쓰는 동기 접근(user_db)은 system/db 것을 그대로 재사용한다.

연결 전략은 system/bot/run.py와 동일하게 맞춘다: 서버에서 실행되면 로컬 MongoDB에
바로 붙고, 그 밖에서(로컬 개발) 실행되면 SSH 터널을 새로 연다.
"""

import os
import socket
import warnings

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

from system.db import user_db, user_logs_db, get_user_names  # noqa: F401  (재수출)

load_dotenv()

MODE = int(os.getenv("MODE", 1))

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

_db_name = "ahp_dev" if MODE == 0 else "ahp"
ahp_db = _client[_db_name]

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
    """앱 시작 시 1회 호출. 존재해도 재실행 시 에러 없이 통과한다."""
    await responses_db.create_index(
        [("collection_id", 1), ("respondent_id", 1)], unique=True
    )
    await submissions_db.create_index(
        [("collection_id", 1), ("respondent_id", 1), ("round", 1)]
    )
    # code_hash가 null인 문서(오프라인에서 관리자가 직접 추가한 응답자)는 몇 명이든
    # 있을 수 있다. sparse=True는 필드가 "존재하되 null"인 경우엔 걸러주지 않아서
    # (필드 자체가 없을 때만 걸러진다) 첫 배포 때 이 값으로 두 번째 수동 응답자를
    # 추가하자마자 충돌이 났다. 실제로 null을 제외하려면 partialFilterExpression으로
    # code_hash가 문자열(진짜 코드)인 문서에만 유니크 제약을 걸어야 한다.
    await respondents_db.create_index(
        [("collection_id", 1), ("code_hash", 1)],
        unique=True,
        partialFilterExpression={"code_hash": {"$type": "string"}},
    )
    await collections_db.create_index("access_token", unique=True, sparse=True)
    await hierarchies_db.create_index([("project_id", 1), ("version", 1)])
    await surveys_db.create_index([("project_id", 1), ("version", 1)])
