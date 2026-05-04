from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import List
import logging
from db import client, crawler_db_name, load_proxy_list, user_db, crawler_db
from common.req import set_proxy_list
import jwt
import os

router = APIRouter()
logger = logging.getLogger(__name__)

class ProxyUpdatePayload(BaseModel):
    proxies: List[str]

@router.post("/proxy/update")
def update_proxy_list(payload: ProxyUpdatePayload, x_internal_key: str = Header(None)):
    token = x_internal_key
    try:
        token_payload = jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=[os.getenv("JWT_ALGORITHM")])
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

    user = user_db.find_one({"uid": token_payload["sub"]}, {"_id": 0})

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if token_payload.get("device") not in user.get("device_list", []):
        raise HTTPException(status_code=403, detail="Device not registered")
    
    try:
        collection = crawler_db['ip-list']
        collection.update_one(
            {"_id": "proxy_list"},
            {"$set": {"list": payload.proxies}},
            upsert=True
        )

        set_proxy_list(payload.proxies)
        
        logger.info(f"프록시 리스트 업데이트 및 갱신 완료: {len(payload.proxies)}개")
        return {"status": "ok", "count": len(payload.proxies)}
        
    except Exception as e:
        logger.error(f"프록시 업데이트 중 서버 에러: {e}")
        raise HTTPException(status_code=500, detail=str(e))