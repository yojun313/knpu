import jwt
import os
from jwt import PyJWTError
from dotenv import load_dotenv
import logging

load_dotenv()

logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("JWT_SECRET")
ALGORITHM = os.getenv("JWT_ALGORITHM")


def verify_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except PyJWTError as e:
        logger.debug(f"토큰 검증 실패: {type(e).__name__}: {e}")
        return None
