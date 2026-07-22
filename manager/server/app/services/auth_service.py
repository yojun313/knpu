import random
import os
import jwt
from datetime import datetime
from fastapi.responses import JSONResponse
from app.db import user_db, auth_db
from app.libs.exceptions import NotFoundException, UnauthorizedException
from app.utils.mail import sendEmail
from app.services.user_service import get_all_admins
from app.utils.pushover import sendPushOver
from dotenv import load_dotenv

load_dotenv()


def request_verify(name: str):
    existing_user = user_db.find_one({"name": name}, {"_id": 0})
    if not existing_user:
        raise NotFoundException("User not found")

    name = existing_user["name"]
    email = existing_user["email"]
    random_pw = "".join(random.choices("0123456789", k=6))

    auth_db.update_one(
        {"email": email, "type": "app_code"},
        {"$set": {"code": random_pw, "name": name, "created_at": datetime.now()}},
        upsert=True,
    )

    msg = f"사용자: {name}\n인증 번호 '{random_pw}'를 입력하십시오"
    sendEmail(email, "[MANAGER] 디바이스 등록 인증번호", msg)

    return JSONResponse(
        status_code=200,
        content={
            "uid": existing_user["uid"],
            "message": "Verification code sent",
            "email": email,
        },
    )


def verify_code(name: str, code: str, device: str):
    existing_user = user_db.find_one({"name": name}, {"_id": 0})
    if not existing_user:
        raise NotFoundException("User not found")

    email = existing_user["email"]

    # 💡 호환성을 위해 type: "app_code"로 검색
    auth_data = auth_db.find_one({"email": email, "type": "app_code"}, {"_id": 0})
    if not auth_data or auth_data["code"] != code:
        raise UnauthorizedException("Invalid verification code")

    token_data = {
        "sub": existing_user["uid"],
        "name": existing_user["name"],
        "device": device,
    }

    user_db.update_one(
        {"uid": existing_user["uid"]}, {"$addToSet": {"device_list": device}}
    )

    auth_db.delete_one({"email": email, "type": "app_code"})

    access_token = create_access_token(token_data)
    admins = [admin["pushoverKey"] for admin in get_all_admins()]
    sendPushOver(
        f"[ User login ]\nUser: {existing_user['name']}\nDevice: {device}", admins
    )

    return JSONResponse(
        status_code=200,
        content={
            "message": "Verification successful",
            "access_token": access_token,
            "user": existing_user,
        },
    )


def loginWithToken(token: str):
    try:
        payload = jwt.decode(
            token, os.getenv("JWT_SECRET"), algorithms=[os.getenv("JWT_ALGORITHM")]
        )
        user = user_db.find_one({"uid": payload["sub"]}, {"_id": 0})
        if not user:
            raise NotFoundException("User not found")

        if payload["device"] not in user.get("device_list", []):
            raise NotFoundException("Device not registered")

        return JSONResponse(
            status_code=200, content={"message": "Login successful", "user": user}
        )
    except jwt.InvalidTokenError:
        raise NotFoundException("Invalid token")


def get_uid_from_bearer(authorization: str | None) -> str | None:
    """'Bearer <token>' 헤더에서 uid를 뽑아낸다. 실패하면 None (호출부는 인증 실패를
    막지 않고 그냥 uid 없이 진행 — 네트워크 분석 자체는 로그인 여부와 무관하게 동작해야 함)."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[len("Bearer ") :]
    try:
        payload = jwt.decode(
            token, os.getenv("JWT_SECRET"), algorithms=[os.getenv("JWT_ALGORITHM")]
        )
        return payload.get("sub")
    except jwt.InvalidTokenError:
        return None


def create_access_token(data: dict):
    encoded_jwt = jwt.encode(
        data, os.getenv("JWT_SECRET"), algorithm=os.getenv("JWT_ALGORITHM")
    )
    return encoded_jwt
