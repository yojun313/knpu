"""웹소켓 허브 — 워커 1개(PLAN.md 7.1)를 전제로 파이썬 딕셔너리를 그대로
공유 상태로 쓴다. Redis나 pub/sub이 없다. manager/web(포트 8080)이 이미
같은 구조로 운영 중인 검증된 패턴이다.

두 웹소켓(admin 콘솔·respondent)은 인증 이후 전부 "서버 → 클라이언트" 단방향
푸시만 받는다 — 클라이언트가 뭔가를 쓰는 동작(응답 저장, 문항 수정)은 전부
이미 검증된 HTTP 엔드포인트를 그대로 쓰고, 그 HTTP 핸들러가 성공한 뒤 이
허브로 push만 위임한다. 그래서 이 파일에 메시지 타입 분기 로직이 없다 —
join/leave/publish 세 가지만 하면 된다.
"""

from __future__ import annotations

from collections import defaultdict

from fastapi import WebSocket


class Hub:
    def __init__(self):
        self._rooms: dict[str, set[WebSocket]] = defaultdict(set)
        self._roles: dict[WebSocket, str] = {}

    async def join(self, room_id: str, ws: WebSocket, role: str):
        """ws.accept()는 호출부 책임이다 — 응답자 소켓은 accept 이후 도착하는
        첫 메시지(auth 토큰)를 봐야 role(=respondent_id)을 알 수 있어서, 이
        함수 안에서 accept까지 같이 해버리면 그 순서를 강제할 수 없다."""
        self._rooms[room_id].add(ws)
        self._roles[ws] = role
        if role.startswith("respondent:"):
            await self.publish(
                room_id,
                "presence",
                {"respondent_id": role.split(":", 1)[1], "online": True},
                only_role_prefix="admin",
            )

    async def leave(self, room_id: str, ws: WebSocket):
        role = self._roles.pop(ws, None)
        self._rooms.get(room_id, set()).discard(ws)
        if not self._rooms.get(room_id):
            self._rooms.pop(room_id, None)
        if role and role.startswith("respondent:"):
            await self.publish(
                room_id,
                "presence",
                {"respondent_id": role.split(":", 1)[1], "online": False},
                only_role_prefix="admin",
            )

    def online_respondents(self, room_id: str) -> set[str]:
        out = set()
        for ws in self._rooms.get(room_id, ()):
            role = self._roles.get(ws, "")
            if role.startswith("respondent:"):
                out.add(role.split(":", 1)[1])
        return out

    async def publish(
        self,
        room_id: str,
        event: str,
        payload: dict,
        *,
        only_role_prefix: str | None = None,
    ):
        """room의 접속자에게 이벤트를 보낸다. 나중에 워커를 늘려야 하면 이
        함수 내부만 Redis pub/sub으로 바꾸면 되고 호출부는 안 건드려도 된다."""
        dead = []
        for ws in list(self._rooms.get(room_id, ())):
            if only_role_prefix and not self._roles.get(ws, "").startswith(
                only_role_prefix
            ):
                continue
            try:
                await ws.send_json({"event": event, **payload})
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.leave(room_id, ws)


hub = Hub()
