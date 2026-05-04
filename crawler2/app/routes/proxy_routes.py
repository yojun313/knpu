from fastapi import APIRouter
from db import load_proxy_list
from common.req import set_proxy_list
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/proxy/reload")
def reload_proxy_list():
    """MongoDB의 ip-list에서 프록시 목록을 읽어 메모리에 적재"""
    try:
        proxy_list = load_proxy_list()
        set_proxy_list(proxy_list)
        logger.info(f"프록시 목록 갱신 완료: {len(proxy_list)}개")
        return {"status": "ok", "count": len(proxy_list)}
    except Exception as e:
        logger.error(f"프록시 목록 갱신 실패: {e}")
        return {"status": "error", "message": str(e)}
