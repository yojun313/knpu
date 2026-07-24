import random
import uuid
from datetime import datetime, timedelta

from fastapi import HTTPException

from app.db import users_db, auth_codes_db
from app.auth.hashing import hash_password, verify_password
from app.auth.jwt import create_token
from app.auth.email import sendEmail

CODE_TTL_MINUTES = 10


def _generate_code() -> str:
    return "".join(random.choices("0123456789", k=6))


def _public_user(user: dict) -> dict:
    return {
        "uid": user["uid"],
        "username": user["username"],
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "status": user["status"],
        "email_verified": user["email_verified"],
        "pushover_key": user.get("pushover_key"),
    }


def signup(data) -> dict:
    if users_db.find_one({"username": data.username}):
        raise HTTPException(status_code=409, detail="이미 사용 중인 아이디입니다")
    if users_db.find_one({"email": data.email}):
        raise HTTPException(status_code=409, detail="이미 사용 중인 이메일입니다")
    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="비밀번호는 8자 이상이어야 합니다")

    now = datetime.now()
    user = {
        "uid": str(uuid.uuid4()),
        "username": data.username,
        "name": data.name,
        "email": data.email,
        "password_hash": hash_password(data.password),
        "role": "member",
        "status": "pending_email",
        "email_verified": False,
        "pushover_key": data.pushover_key,
        "created_at": now,
        "approved_at": None,
        "approved_by": None,
        "updated_at": now,
    }
    users_db.insert_one(user)
    _send_signup_code(data.username, data.email)

    return {"message": "가입 요청이 접수되었습니다. 이메일로 전송된 인증번호를 입력해주세요"}


def _send_signup_code(username: str, email: str):
    code = _generate_code()
    auth_codes_db.update_one(
        {"email": email, "type": "signup"},
        {
            "$set": {
                "username": username,
                "code": code,
                "expires_at": datetime.now() + timedelta(minutes=CODE_TTL_MINUTES),
            }
        },
        upsert=True,
    )
    sendEmail(
        email,
        "[KNPU] 이메일 인증번호",
        f"{username}님, KNPU 랩 시스템 가입 인증번호는 다음과 같습니다.\n\n{code}\n\n"
        f"{CODE_TTL_MINUTES}분 이내에 입력해주세요.",
    )


def resend_signup_code(username: str) -> dict:
    user = users_db.find_one({"username": username})
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    if user["status"] != "pending_email":
        raise HTTPException(status_code=400, detail="이미 이메일 인증이 완료된 계정입니다")

    _send_signup_code(username, user["email"])
    return {"message": "인증번호를 다시 전송했습니다"}


def verify_email(data) -> dict:
    user = users_db.find_one({"username": data.username})
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

    code_doc = auth_codes_db.find_one({"email": user["email"], "type": "signup"})
    if not code_doc or code_doc["code"] != data.code:
        raise HTTPException(status_code=401, detail="인증번호가 올바르지 않습니다")
    if code_doc["expires_at"] < datetime.now():
        raise HTTPException(status_code=401, detail="인증번호가 만료되었습니다")

    users_db.update_one(
        {"username": data.username},
        {
            "$set": {
                "email_verified": True,
                "status": "pending_approval",
                "updated_at": datetime.now(),
            }
        },
    )
    auth_codes_db.delete_one({"_id": code_doc["_id"]})

    return {
        "message": "이메일 인증이 완료되었습니다. 관리자 승인 후 로그인할 수 있습니다"
    }


def login(data) -> dict:
    user = users_db.find_one({"username": data.username})
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다")

    if user["status"] == "pending_email":
        raise HTTPException(status_code=403, detail="이메일 인증을 먼저 완료해주세요")
    if user["status"] == "pending_approval":
        raise HTTPException(status_code=403, detail="관리자 승인 대기 중입니다")
    if user["status"] == "rejected":
        raise HTTPException(status_code=403, detail="가입이 거절된 계정입니다")

    token = create_token(user)
    return {"token": token, "user": _public_user(user)}


def get_profile(uid: str) -> dict:
    user = users_db.find_one({"uid": uid})
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    return _public_user(user)


def update_profile(uid: str, data) -> dict:
    user = users_db.find_one({"uid": uid})
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

    updates = {}
    if data.name:
        updates["name"] = data.name
    if data.pushover_key is not None:
        updates["pushover_key"] = data.pushover_key

    if data.new_password:
        if not data.current_password or not verify_password(
            data.current_password, user["password_hash"]
        ):
            raise HTTPException(status_code=401, detail="현재 비밀번호가 올바르지 않습니다")
        if len(data.new_password) < 8:
            raise HTTPException(status_code=400, detail="비밀번호는 8자 이상이어야 합니다")
        updates["password_hash"] = hash_password(data.new_password)

    if updates:
        updates["updated_at"] = datetime.now()
        users_db.update_one({"uid": uid}, {"$set": updates})

    return get_profile(uid)


def forgot_password(username: str) -> dict:
    user = users_db.find_one({"username": username})
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

    code = _generate_code()
    auth_codes_db.update_one(
        {"email": user["email"], "type": "reset"},
        {
            "$set": {
                "username": username,
                "code": code,
                "expires_at": datetime.now() + timedelta(minutes=CODE_TTL_MINUTES),
            }
        },
        upsert=True,
    )
    sendEmail(
        user["email"],
        "[KNPU] 비밀번호 재설정 인증번호",
        f"{username}님, 비밀번호 재설정 인증번호는 다음과 같습니다.\n\n{code}\n\n"
        f"{CODE_TTL_MINUTES}분 이내에 입력해주세요.",
    )
    return {"message": "비밀번호 재설정 인증번호를 전송했습니다"}


def reset_password(data) -> dict:
    user = users_db.find_one({"username": data.username})
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

    code_doc = auth_codes_db.find_one({"email": user["email"], "type": "reset"})
    if not code_doc or code_doc["code"] != data.code:
        raise HTTPException(status_code=401, detail="인증번호가 올바르지 않습니다")
    if code_doc["expires_at"] < datetime.now():
        raise HTTPException(status_code=401, detail="인증번호가 만료되었습니다")
    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="비밀번호는 8자 이상이어야 합니다")

    users_db.update_one(
        {"username": data.username},
        {
            "$set": {
                "password_hash": hash_password(data.new_password),
                "updated_at": datetime.now(),
            }
        },
    )
    auth_codes_db.delete_one({"_id": code_doc["_id"]})

    return {"message": "비밀번호가 재설정되었습니다"}


def list_pending_requests() -> list:
    docs = list(users_db.find({"status": "pending_approval"}))
    return [_public_user(d) for d in docs]


def approve_request(uid: str, admin_uid: str) -> dict:
    user = users_db.find_one({"uid": uid})
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    if user["status"] != "pending_approval":
        raise HTTPException(status_code=400, detail="승인 대기 상태가 아닙니다")

    users_db.update_one(
        {"uid": uid},
        {
            "$set": {
                "status": "approved",
                "approved_at": datetime.now(),
                "approved_by": admin_uid,
                "updated_at": datetime.now(),
            }
        },
    )
    sendEmail(
        user["email"],
        "[KNPU] 가입이 승인되었습니다",
        f"{user['name']}님, KNPU 랩 시스템 가입이 승인되었습니다. "
        f"이제 knpu.re.kr에서 로그인할 수 있습니다.",
    )
    return {"message": "승인 완료"}


def reject_request(uid: str) -> dict:
    user = users_db.find_one({"uid": uid})
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    if user["status"] != "pending_approval":
        raise HTTPException(status_code=400, detail="승인 대기 상태가 아닙니다")

    users_db.update_one(
        {"uid": uid},
        {"$set": {"status": "rejected", "updated_at": datetime.now()}},
    )
    sendEmail(
        user["email"],
        "[KNPU] 가입 요청이 거절되었습니다",
        f"{user['name']}님, KNPU 랩 시스템 가입 요청이 거절되었습니다. "
        f"문의 사항은 관리자에게 연락해주세요.",
    )
    return {"message": "거절 완료"}
