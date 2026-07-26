from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import List
import logging
from db import crawler_db
from common.req import set_proxy_list

router = APIRouter()
logger = logging.getLogger(__name__)


class ProxyUpdatePayload(BaseModel):
    proxies: List[str]


@router.post("/proxy/update")
def update_proxy_list(payload: ProxyUpdatePayload):
    try:
        collection = crawler_db["ip-list"]
        collection.update_one(
            {"_id": "proxy_list"}, {"$set": {"list": payload.proxies}}, upsert=True
        )

        set_proxy_list(payload.proxies)

        logger.info(f"프록시 리스트 업데이트 및 갱신 완료: {len(payload.proxies)}개")
        return {"status": "ok", "count": len(payload.proxies)}

    except Exception as e:
        logger.error(f"프록시 업데이트 중 서버 에러: {e}")
        raise HTTPException(status_code=500, detail=str(e))
