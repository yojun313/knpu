import time
import random
import string
import logging

logger = logging.getLogger(__name__)

# 인증코드 저장소 (메모리)
# { "최우철": {"code": "482951", "email": "choi@knpu.ac.kr", "expires": 1711234567.0, "uid": "abc123"} }
_codes: dict[str, dict] = {}

CODE_TTL = 300  # 5분


def generate_code(name: str, email: str, uid: str) -> str:
    """6자리 인증코드 생성 및 저장"""
    code = ''.join(random.choices(string.digits, k=6))
    _codes[name] = {
        "code": code,
        "email": email,
        "uid": uid,
        "expires": time.time() + CODE_TTL,
    }
    logger.info(f"인증코드 생성: {name} → {email}")
    return code


def verify_code(name: str, code: str) -> dict | None:
    """
    인증코드 검증
    성공 → {"uid": "abc123", "name": "최우철"} 반환, 코드 삭제
    실패 → None
    """
    entry = _codes.get(name)
    if not entry:
        return None

    # 만료 확인
    if time.time() > entry["expires"]:
        del _codes[name]
        return None

    # 코드 일치 확인
    if entry["code"] != code:
        return None

    # 성공 → 코드 삭제 (1회용)
    user_data = {"uid": entry["uid"], "name": name}
    del _codes[name]
    return user_data


def cleanup_expired():
    """만료된 코드 정리"""
    now = time.time()
    expired = [k for k, v in _codes.items() if now > v["expires"]]
    for k in expired:
        del _codes[k]
