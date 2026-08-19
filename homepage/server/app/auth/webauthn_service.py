from datetime import datetime, timedelta

from fastapi import HTTPException
from webauthn import (
    base64url_to_bytes,
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import bytes_to_base64url, parse_client_data_json
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.auth.jwt import create_token
from app.auth.service import _log_user_activity, _public_user
from app.auth.webauthn_config import (
    CHALLENGE_TTL_MINUTES,
    EXPECTED_ORIGINS,
    RP_ID,
    RP_NAME,
)
from app.db import users_db, webauthn_challenges_db, webauthn_credentials_db


def _save_challenge(challenge: bytes, purpose: str, user_uid: str | None) -> None:
    webauthn_challenges_db.insert_one(
        {
            "_id": bytes_to_base64url(challenge),
            "purpose": purpose,
            "user_uid": user_uid,
            "expires_at": datetime.now() + timedelta(minutes=CHALLENGE_TTL_MINUTES),
        }
    )


def _pop_challenge(challenge_b64: str, purpose: str) -> dict | None:
    doc = webauthn_challenges_db.find_one_and_delete({"_id": challenge_b64})
    if not doc or doc.get("purpose") != purpose:
        return None
    if doc["expires_at"] < datetime.now():
        return None
    return doc


def _extract_challenge_b64(credential: dict) -> str:
    try:
        client_data_json = base64url_to_bytes(credential["response"]["clientDataJSON"])
        client_data = parse_client_data_json(client_data_json)
        return bytes_to_base64url(client_data.challenge)
    except Exception:
        raise HTTPException(status_code=400, detail="잘못된 패스키 응답입니다")


def get_registration_options(user_uid: str) -> str:
    user = users_db.find_one({"uid": user_uid})
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

    existing = list(webauthn_credentials_db.find({"user_uid": user_uid}, {"_id": 1}))
    exclude_credentials = [
        PublicKeyCredentialDescriptor(id=base64url_to_bytes(c["_id"])) for c in existing
    ]

    options = generate_registration_options(
        rp_id=RP_ID,
        rp_name=RP_NAME,
        user_id=user_uid.encode("utf-8"),
        user_name=user["username"],
        user_display_name=user["name"],
        exclude_credentials=exclude_credentials or None,
        # resident_key=REQUIRED로 두면 디스커버러블 자격 증명을 지원하지 않는
        # 인증기(플랫폼 생체인증이 설정 안 돼 있거나 오래된 보안키 등)에서는
        # navigator.credentials.create() 자체가 NotAllowedError로 즉시 실패해버려
        # 사용자에게는 "아무 반응 없음"으로 보인다. PREFERRED로 두면 지원하는
        # 인증기에서는 그대로 디스커버러블(진짜 패스키)로 등록되고, 지원 안 하는
        # 인증기에서도 등록 자체는 성공한다(그 경우만 로그인 시 아이디가 필요).
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )

    _save_challenge(options.challenge, purpose="registration", user_uid=user_uid)
    return options_to_json(options)


def verify_registration(
    user_uid: str, credential: dict, device_name: str | None
) -> dict:
    challenge_b64 = _extract_challenge_b64(credential)
    stored = _pop_challenge(challenge_b64, purpose="registration")
    if not stored or stored.get("user_uid") != user_uid:
        raise HTTPException(
            status_code=400,
            detail="등록 요청이 만료되었거나 올바르지 않습니다. 다시 시도해주세요",
        )

    try:
        verification = verify_registration_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(challenge_b64),
            expected_rp_id=RP_ID,
            expected_origin=EXPECTED_ORIGINS,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"패스키 등록에 실패했습니다: {e}")

    credential_id_b64 = bytes_to_base64url(verification.credential_id)
    if webauthn_credentials_db.find_one({"_id": credential_id_b64}):
        raise HTTPException(status_code=409, detail="이미 등록된 패스키입니다")

    now = datetime.now()
    webauthn_credentials_db.insert_one(
        {
            "_id": credential_id_b64,
            "user_uid": user_uid,
            "public_key": verification.credential_public_key,
            "sign_count": verification.sign_count,
            "transports": (credential.get("response") or {}).get("transports") or [],
            "device_name": (device_name or "").strip()[:60] or "패스키",
            "backed_up": bool(verification.credential_backed_up),
            "created_at": now,
            "last_used_at": None,
        }
    )
    _log_user_activity(
        user_uid,
        "homepage.passkey.register",
        f"패스키 등록: {(device_name or '').strip() or '이름 없음'}",
    )

    return {"message": "패스키가 등록되었습니다"}


def get_authentication_options() -> str:
    options = generate_authentication_options(
        rp_id=RP_ID,
        user_verification=UserVerificationRequirement.PREFERRED,
        # allow_credentials를 지정하지 않으면 브라우저가 이 rp_id로 등록된 패스키
        # 중 사용자가 직접 고르게 한다(아이디 입력 없는 진짜 패스키 로그인)
    )
    _save_challenge(options.challenge, purpose="authentication", user_uid=None)
    return options_to_json(options)


def verify_authentication(credential: dict) -> dict:
    credential_id_b64 = credential.get("id")
    if not credential_id_b64:
        raise HTTPException(status_code=400, detail="잘못된 패스키 응답입니다")

    stored_cred = webauthn_credentials_db.find_one({"_id": credential_id_b64})
    if not stored_cred:
        raise HTTPException(status_code=401, detail="등록되지 않은 패스키입니다")

    challenge_b64 = _extract_challenge_b64(credential)
    stored_challenge = _pop_challenge(challenge_b64, purpose="authentication")
    if not stored_challenge:
        raise HTTPException(
            status_code=400, detail="로그인 요청이 만료되었습니다. 다시 시도해주세요"
        )

    try:
        verification = verify_authentication_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(challenge_b64),
            expected_rp_id=RP_ID,
            expected_origin=EXPECTED_ORIGINS,
            credential_public_key=bytes(stored_cred["public_key"]),
            credential_current_sign_count=stored_cred["sign_count"],
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"패스키 인증에 실패했습니다: {e}")

    user = users_db.find_one({"uid": stored_cred["user_uid"]})
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")

    # 비밀번호 로그인과 동일한 계정 상태 검사(service.login 참고) — 패스키라고 우회되면 안 된다
    if user["status"] == "pending_email":
        raise HTTPException(status_code=403, detail="이메일 인증을 먼저 완료해주세요")
    if user["status"] == "pending_approval":
        raise HTTPException(status_code=403, detail="관리자 승인 대기 중입니다")
    if user["status"] == "rejected":
        raise HTTPException(status_code=403, detail="가입이 거절된 계정입니다")

    now = datetime.now()
    webauthn_credentials_db.update_one(
        {"_id": credential_id_b64},
        {"$set": {"sign_count": verification.new_sign_count, "last_used_at": now}},
    )

    token = create_token(user)
    try:
        _log_user_activity(
            user["uid"], "homepage.auth.login_passkey", "Homepage login (passkey)"
        )
    except Exception:
        pass

    return {"token": token, "user": _public_user(user)}


def list_passkeys(user_uid: str) -> list[dict]:
    docs = webauthn_credentials_db.find(
        {"user_uid": user_uid},
        {"public_key": 0, "sign_count": 0},
    ).sort("created_at", -1)

    result = []
    for d in docs:
        result.append(
            {
                "credential_id": d["_id"],
                "device_name": d.get("device_name") or "패스키",
                "backed_up": bool(d.get("backed_up")),
                "created_at": d["created_at"].strftime("%Y-%m-%d %H:%M"),
                "last_used_at": d["last_used_at"].strftime("%Y-%m-%d %H:%M")
                if d.get("last_used_at")
                else None,
            }
        )
    return result


def delete_passkey(user_uid: str, credential_id: str) -> dict:
    result = webauthn_credentials_db.delete_one(
        {"_id": credential_id, "user_uid": user_uid}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="패스키를 찾을 수 없습니다")
    _log_user_activity(user_uid, "homepage.passkey.delete", "패스키 삭제")
    return {"message": "패스키가 삭제되었습니다"}
