from pymongo.errors import OperationFailure

# Keep service-specific helpers and indexes here; names/connections are shared.
from system.db import user_db, user_logs_db, get_user_names  # noqa: F401
from system.db.mcdm import (  # noqa: F401
    DB_NAME,
    mongo_client,
    _client,
    mcdm_db,
    ahp_db,
    projects_db,
    hierarchies_db,
    surveys_db,
    collections_db,
    respondents_db,
    responses_db,
    submissions_db,
    results_db,
    imports_db,
)


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
