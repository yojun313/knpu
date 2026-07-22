import time
import random
import string
import logging

logger = logging.getLogger(__name__)

_codes: dict[str, dict] = {}

CODE_TTL = 300  # 5분


def generate_code(name: str, email: str, uid: str) -> str:
    code = "".join(random.choices(string.digits, k=6))
    _codes[name] = {
        "code": code,
        "email": email,
        "uid": uid,
        "expires": time.time() + CODE_TTL,
    }
    logger.info(f"인증코드 생성: {name} → {email}")
    return code


def verify_code(name: str, code: str) -> dict | None:
    entry = _codes.get(name)
    if not entry:
        return None

    if time.time() > entry["expires"]:
        del _codes[name]
        return None

    if entry["code"] != code:
        return None

    user_data = {"uid": entry["uid"], "name": name}
    del _codes[name]
    return user_data
