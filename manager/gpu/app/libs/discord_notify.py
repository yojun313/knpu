"""Discord 알림 발행기 (프록시).

이 서비스는 자체 MongoDB 접속 정보를 갖지 않으므로, 이미 떠 있는 manager/server의
관리자 알림 엔드포인트(POST /users/admin/notify)를 통해 알림을 큐에 넣는다.
실제 전송은 manager/server -> discord.notifications 컬렉션 -> 디스코드 봇 순서로 처리된다.
"""

import os

import requests

from system.endpoints import internal_api

# 기본값이 홈페이지 포트(8000)로 잘못 잡혀 있어서 이 프록시의 알림이 조용히 404로
# 사라지고 있었다 — /users/admin/notify는 manager/server(8001, dev 18001)의 것이다.
MANAGER_SERVER_INTERNAL_API = os.getenv(
    "MANAGER_SERVER_INTERNAL_API", internal_api("manager")
)


def notify_discord(channel_key: str, content: str) -> None:
    try:
        kind = "error" if channel_key == "system_error" else "ops"
        requests.post(
            f"{MANAGER_SERVER_INTERNAL_API}/users/admin/notify",
            json={"message": content, "kind": kind},
            timeout=5,
        )
    except Exception:
        pass
