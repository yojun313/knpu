import random
import secrets
import uuid
from datetime import datetime, timedelta

from fastapi import HTTPException

from app.db import (
    users_db,
    auth_codes_db,
    members_db,
    manager_users_db,
    user_logs_db,
    webauthn_credentials_db,
)
from app.auth.hashing import hash_password, verify_password
from app.auth.jwt import create_token
from app.auth.email import sendEmail
from app.auth.webauthn_config import EXPECTED_ORIGIN
from app.libs import r2
from app.libs.discord_notify import notify_discord
from shared.user_log import insert_log

CODE_TTL_MINUTES = 10
SIGNUP_LINK_TTL_MINUTES = 30


def _log_user_activity(user_uid: str, action: str, message: str, **kwargs) -> None:
    insert_log(user_logs_db, user_uid, action, "homepage", message=message, **kwargs)


def _generate_code() -> str:
    return "".join(random.choices("0123456789", k=6))


def _generate_token() -> str:
    return secrets.token_urlsafe(32)


def _public_user(user: dict) -> dict:
    return {
        "uid": user["uid"],
        "username": user["username"],
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "status": user["status"],
        "email_verified": user["email_verified"],
        "member_uid": user.get("member_uid"),
    }


def _match_member(name: str) -> dict | None:
    matches = list(members_db.find({"name": name}))
    return matches[0] if len(matches) == 1 else None


def _member_already_linked(member_uid: str) -> bool:
    return (
        users_db.find_one({"member_uid": member_uid, "status": {"$ne": "rejected"}})
        is not None
    )


def _match_manager_account(name: str) -> dict | None:
    matches = list(manager_users_db.find({"name": name}))
    return matches[0] if len(matches) == 1 else None


def _manager_uid_already_used(uid: str) -> bool:
    return users_db.find_one({"uid": uid, "status": {"$ne": "rejected"}}) is not None


def _manager_account_exists_by_email(email: str) -> bool:
    return manager_users_db.find_one({"email": email}) is not None


def signup(data) -> dict:
    # 이메일 인증을 끝내지 못하고 이탈한(pending_email) 기존 기록은 "선점"으로 치지 않고
    # 새 가입 신청으로 덮어써서, 같은 아이디로 재시도할 수 있게 한다.
    existing_username = users_db.find_one({"username": data.username})
    if existing_username and existing_username["status"] != "pending_email":
        raise HTTPException(status_code=409, detail="이미 사용 중인 아이디입니다")

    existing_email = users_db.find_one({"email": data.email})
    if existing_email and existing_email["username"] != data.username:
        if existing_email["status"] != "pending_email":
            raise HTTPException(status_code=409, detail="이미 사용 중인 이메일입니다")
        # 다른 아이디로 인증을 끝내지 못하고 이탈한 기록이 이 이메일을 물고 있던 것 — 정리
        users_db.delete_one({"_id": existing_email["_id"]})

    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="비밀번호는 8자 이상이어야 합니다")

    # 홈페이지 멤버 목록에 이미 등록된 이름이면 해당 멤버 프로필과 연결한다 — 연결되면
    # 이메일 인증만으로 바로 승인되고(관리자 승인 불필요), 마이페이지에서 그 멤버의
    # 프로필 사진을 편집할 수 있게 된다.
    matched_member = _match_member(data.name)
    member_uid = None
    if matched_member and not _member_already_linked(matched_member["uid"]):
        member_uid = matched_member["uid"]

    # manager.users에 같은 이름의 계정이 이미 있으면 uid를 그대로 이어받아, 두 시스템에서
    # 같은 사람이 항상 같은 uid로 식별되게 한다 (crawler db-list 소유자 확인 등에 필요).
    matched_manager_account = _match_manager_account(data.name)
    manager_uid = None
    if matched_manager_account and not _manager_uid_already_used(
        matched_manager_account["uid"]
    ):
        manager_uid = matched_manager_account["uid"]

    # manager.users에 같은 이메일로 이미 가입 이력이 있으면(=이미 검증된 랩 구성원) 관리자
    # 승인 없이 바로 가입 승인한다. 이름과 달리 이메일은 동명이인 걱정이 없어 곧바로 신뢰한다.
    manager_email_matched = _manager_account_exists_by_email(data.email)

    now = datetime.now()
    user = {
        "uid": (
            existing_username["uid"]
            if existing_username
            else manager_uid or str(uuid.uuid4())
        ),
        "username": data.username,
        "name": data.name,
        "email": data.email,
        "password_hash": hash_password(data.password),
        "role": "member",
        "status": "pending_email",
        "email_verified": False,
        "member_uid": member_uid,
        "manager_email_matched": manager_email_matched,
        "created_at": existing_username["created_at"] if existing_username else now,
        "approved_at": None,
        "approved_by": None,
        "updated_at": now,
    }
    users_db.update_one({"username": data.username}, {"$set": user}, upsert=True)
    _send_signup_verification_link(data.username, data.email)
    _log_user_activity(
        user["uid"],
        "homepage.auth.signup",
        f"회원가입 신청: {data.name} (@{data.username})",
    )

    return {
        "message": "가입 요청이 접수되었습니다. 이메일로 전송된 인증 링크를 눌러주세요"
    }


def _send_signup_verification_link(username: str, email: str):
    token = _generate_token()
    auth_codes_db.update_one(
        {"email": email, "type": "signup"},
        {
            "$set": {
                "username": username,
                "token": token,
                "expires_at": datetime.now()
                + timedelta(minutes=SIGNUP_LINK_TTL_MINUTES),
            }
        },
        upsert=True,
    )
    verify_url = f"{EXPECTED_ORIGIN}/verify-email?token={token}"
    sendEmail(
        email,
        "[KNPU] 이메일 인증",
        f"{username}님, 아래 링크를 클릭하면 KNPU 랩 시스템 가입 이메일 인증이 완료됩니다.\n\n"
        f"{verify_url}\n\n{SIGNUP_LINK_TTL_MINUTES}분 이내에 클릭해주세요.",
    )


def resend_signup_code(username: str) -> dict:
    user = users_db.find_one({"username": username})
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    if user["status"] != "pending_email":
        raise HTTPException(
            status_code=400, detail="이미 이메일 인증이 완료된 계정입니다"
        )

    _send_signup_verification_link(username, user["email"])
    return {"message": "인증 링크를 다시 전송했습니다"}


def verify_email(data) -> dict:
    code_doc = auth_codes_db.find_one({"token": data.token, "type": "signup"})
    if not code_doc:
        raise HTTPException(status_code=401, detail="유효하지 않은 인증 링크입니다")
    if code_doc["expires_at"] < datetime.now():
        raise HTTPException(status_code=401, detail="인증 링크가 만료되었습니다")

    user = users_db.find_one({"username": code_doc["username"]})
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

    # 가입 시 홈페이지 멤버와 연결됐거나, manager.users에 같은 이메일로 가입 이력이 있으면
    # 관리자 승인 없이 바로 승인 처리한다.
    auto_approved = bool(user.get("member_uid")) or bool(
        user.get("manager_email_matched")
    )
    approved_reason = (
        "auto:member_match" if user.get("member_uid") else "auto:manager_email_match"
    )
    updates = {"email_verified": True, "updated_at": datetime.now()}
    if auto_approved:
        updates.update(
            {
                "status": "approved",
                "approved_at": datetime.now(),
                "approved_by": approved_reason,
            }
        )
    else:
        updates["status"] = "pending_approval"

    users_db.update_one({"username": user["username"]}, {"$set": updates})
    auth_codes_db.delete_one({"_id": code_doc["_id"]})
    _log_user_activity(
        user["uid"],
        "homepage.auth.verify_email",
        f"이메일 인증 완료: {user['name']} ({'자동 승인' if auto_approved else '관리자 승인 대기'})",
    )

    notify_discord(
        "admin_ops",
        f"🆕 새 회원가입: {user['name']} (@{user['username']}, {user['email']})"
        + (" — 자동 승인됨" if auto_approved else " — 관리자 승인 대기 중"),
    )

    if auto_approved:
        sendEmail(
            user["email"],
            "[KNPU] 가입이 완료되었습니다",
            f"{user['name']}님, 기존에 등록된 멤버 프로필과 자동으로 연결되어 "
            f"별도 승인 없이 바로 knpu.re.kr에서 로그인할 수 있습니다.",
        )
        return {
            "message": "이메일 인증이 완료되었습니다. 기존 멤버 프로필과 연결되어 바로 로그인할 수 있습니다.",
            "auto_approved": True,
        }

    notify_discord(
        "signup_approval",
        content="",
        embed={
            "title": "📝 새 가입 승인 요청",
            "description": (
                f"**{user['name']}**님이 가입 신청했습니다. 홈페이지 멤버 목록과 자동으로 "
                "연결되지 않아 검토가 필요합니다."
            ),
            "color": 0xFFC800,
            "fields": [
                {"name": "이름", "value": user["name"], "inline": True},
                {"name": "아이디", "value": user["username"], "inline": True},
                {"name": "이메일", "value": user["email"], "inline": False},
                {"name": "UID", "value": f"`{user['uid']}`", "inline": False},
            ],
        },
        actions={"type": "signup_approval", "uid": user["uid"]},
    )

    return {
        "message": "이메일 인증이 완료되었습니다. 관리자 승인 후 로그인할 수 있습니다",
        "auto_approved": False,
    }


def login(data) -> dict:
    user = users_db.find_one({"username": data.username})
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(
            status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다"
        )

    if user["status"] == "pending_email":
        raise HTTPException(status_code=403, detail="이메일 인증을 먼저 완료해주세요")
    if user["status"] == "pending_approval":
        raise HTTPException(status_code=403, detail="관리자 승인 대기 중입니다")
    if user["status"] == "rejected":
        raise HTTPException(status_code=403, detail="가입이 거절된 계정입니다")

    token = create_token(user)

    try:
        _log_user_activity(user["uid"], "homepage.auth.login", "Homepage login")
    except Exception:
        pass

    return {"token": token, "user": _public_user(user)}


def get_profile(uid: str) -> dict:
    user = users_db.find_one({"uid": uid})
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    return _public_user(user)


def get_linked_member(uid: str) -> dict | None:
    user = users_db.find_one({"uid": uid})
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

    member = (
        members_db.find_one({"uid": user["member_uid"]})
        if user.get("member_uid")
        else None
    )

    if not member:
        candidate = _match_member(user["name"])
        if candidate and not _member_already_linked(candidate["uid"]):
            users_db.update_one(
                {"uid": uid},
                {
                    "$set": {
                        "member_uid": candidate["uid"],
                        "updated_at": datetime.now(),
                    }
                },
            )
            member = candidate

    if not member:
        return None
    member["_id"] = str(member["_id"])
    return member


def update_my_member_photo(uid: str, image_url: str) -> dict:
    member = get_linked_member(uid)
    if not member:
        raise HTTPException(
            status_code=400, detail="연결된 멤버 프로필을 찾을 수 없습니다"
        )

    old_image = member.get("image")
    members_db.update_one({"uid": member["uid"]}, {"$set": {"image": image_url}})
    if old_image:
        try:
            r2.delete_object(old_image)
        except Exception:
            pass

    member["image"] = image_url
    _log_user_activity(
        uid, "homepage.member.photo_update", f"프로필 사진 교체: {member.get('name')}"
    )
    return member


def update_profile(uid: str, data) -> dict:
    user = users_db.find_one({"uid": uid})
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

    updates = {}
    if data.name:
        updates["name"] = data.name

    if data.new_password:
        if not data.current_password or not verify_password(
            data.current_password, user["password_hash"]
        ):
            raise HTTPException(
                status_code=401, detail="현재 비밀번호가 올바르지 않습니다"
            )
        if len(data.new_password) < 8:
            raise HTTPException(
                status_code=400, detail="비밀번호는 8자 이상이어야 합니다"
            )
        updates["password_hash"] = hash_password(data.new_password)

    if updates:
        updates["updated_at"] = datetime.now()
        users_db.update_one({"uid": uid}, {"$set": updates})
        field_labels = {"name": "이름", "password_hash": "비밀번호"}
        changed = [field_labels[k] for k in field_labels if k in updates]
        _log_user_activity(
            uid, "homepage.profile.update", "프로필 수정: " + ", ".join(changed)
        )

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
    _log_user_activity(
        user["uid"], "homepage.auth.password_reset", f"비밀번호 재설정: {user['name']}"
    )

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
    _log_user_activity(
        admin_uid,
        "homepage.member_request.approve",
        f"가입 승인: {user['name']} (@{user['username']})",
        target={"type": "user", "id": uid},
    )
    return {"message": "승인 완료"}


def reject_request(uid: str, admin_uid: str) -> dict:
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
    _log_user_activity(
        admin_uid,
        "homepage.member_request.reject",
        f"가입 거절: {user['name']} (@{user['username']})",
        target={"type": "user", "id": uid},
    )
    return {"message": "거절 완료"}


def change_role(uid: str, new_role: str, admin_uid: str) -> dict:
    if new_role not in ("admin", "member"):
        raise HTTPException(
            status_code=400, detail="role은 admin 또는 member여야 합니다"
        )

    user = users_db.find_one({"uid": uid})
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

    if uid == admin_uid and new_role != "admin":
        raise HTTPException(
            status_code=400, detail="자기 자신의 admin 권한은 해제할 수 없습니다"
        )

    users_db.update_one(
        {"uid": uid},
        {"$set": {"role": new_role, "updated_at": datetime.now()}},
    )
    notify_discord(
        "admin_ops",
        f"{user.get('name', user.get('username'))}({user.get('username')})의 역할이 "
        f"{user.get('role')} -> {new_role}(으)로 변경되었습니다 (관리자: {admin_uid})",
    )
    _log_user_activity(
        admin_uid,
        "homepage.user.role_change",
        f"역할 변경: {user.get('name')} ({user.get('role')} -> {new_role})",
        target={"type": "user", "id": uid},
    )
    return {"message": "역할이 변경되었습니다", "role": new_role}


def delete_user(uid: str, admin_uid: str) -> dict:
    user = users_db.find_one({"uid": uid})
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

    if uid == admin_uid:
        raise HTTPException(status_code=400, detail="자기 자신은 삭제할 수 없습니다")

    users_db.delete_one({"uid": uid})
    # 계정에 딸린 부가 데이터(패스키, 미완료 인증/재설정 코드)도 같이 정리해서
    # 삭제 후 같은 아이디로 재가입할 때 고아 데이터가 남지 않게 한다.
    webauthn_credentials_db.delete_many({"user_uid": uid})
    auth_codes_db.delete_many({"username": user["username"]})

    notify_discord(
        "admin_ops",
        f"{user.get('name', user.get('username'))}({user.get('username')}) 계정이 "
        f"삭제되었습니다 (관리자: {admin_uid})",
    )
    _log_user_activity(
        admin_uid,
        "homepage.user.delete",
        f"계정 삭제: {user.get('name')} (@{user.get('username')})",
        target={"type": "user", "id": uid},
        outcome="success",
    )
    return {"message": "삭제되었습니다"}
