"""PolyDecision async database and collection names."""

from .connection import get_async_client
from .names import DATABASE_NAMES

mongo_client = _client = get_async_client()
DB_NAME = DATABASE_NAMES["mcdm"]
mcdm_db = _client[DB_NAME]
ahp_db = mcdm_db  # Compatibility name; always the same database.
projects_db = mcdm_db["projects"]
hierarchies_db = mcdm_db["hierarchies"]
surveys_db = mcdm_db["surveys"]
collections_db = mcdm_db["collections"]
respondents_db = mcdm_db["respondents"]
responses_db = mcdm_db["responses"]
submissions_db = mcdm_db["submissions"]
results_db = mcdm_db["results"]
imports_db = mcdm_db["imports"]
