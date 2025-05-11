from fastapi.responses import JSONResponse
from app.db import user_db, auth_db
from app.utils.mongo import clean_doc
from app.libs.exceptions import NotFoundException
from app.utils.mail import sendEmail
import random
import os
import jwt
from dotenv import load_dotenv

load_dotenv()

def request_verify(name: str):
    existing_user = user_db.find_one({"name": name})
    if not existing_user:
        raise NotFoundException("User not found")
    
    existing_user = clean_doc(existing_user)
    name = existing_user["name"]
    email = existing_user["email"]
    random_pw = ''.join(random.choices('0123456789', k=6))
    
    auth_db.update_one(
        {"email": email},
        {"$set": {"auth_code": random_pw}},
        upsert=True
    )
    
    msg = (
        f"사용자: {name}\n"
        f"인증 번호 '{random_pw}'를 입력하십시오"
    )
    sendEmail(email, "[MANAGER] 디바이스 등록 인증번호", msg)
    
    return JSONResponse(status_code=200, content={"uid": existing_user["uid"], "message": "Verification code sent"})
    
def verify_code(name: str, code: str, device: str):
    existing_user = user_db.find_one({"name": name})
    if not existing_user:
        raise NotFoundException("User not found")
    
    existing_user = clean_doc(existing_user)
    email = existing_user["email"]
    
    auth_data = auth_db.find_one({"email": email})
    if not auth_data or auth_data["auth_code"] != code:
        raise NotFoundException("Invalid verification code")

    token_data = {
        "sub": existing_user["uid"],  # 또는 name/email 등 식별자
        "name": existing_user["name"],
        "device": device,
    }
    user_db.update_one(
        {"uid": existing_user["uid"]},
        {"$addToSet": {"device_list": device}}
    )
    
    access_token = create_access_token(token_data)
        
    return JSONResponse(status_code=200, content={"message": "Verification successful", "access_token": access_token, "user": existing_user})

def loginWithToken(token: str):
    try:
        payload = jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=[os.getenv("JWT_ALGORITHM")])
        user = user_db.find_one({"uid": payload["sub"]})
        if not user:
            raise NotFoundException("User not found")

        if payload["device"] not in user["device_list"]:
            raise NotFoundException("Device not registered")
        
        user = clean_doc(user)
        return JSONResponse(status_code=200, content={"message": "Login successful", "user": user})
    except jwt.InvalidTokenError:
        raise NotFoundException("Invalid token")
    
def create_access_token(data: dict):
    encoded_jwt = jwt.encode(data, os.getenv("JWT_SECRET"), algorithm=os.getenv("JWT_ALGORITHM"))
    return encoded_jwt