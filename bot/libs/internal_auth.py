"""homepage/server의 관리자 전용 API(가입 승인/거절 등)를 봇이 직접 호출할 때 쓰는
내부용 관리자 토큰. homepage/server가 세션 로그인 시 발급하는 JWT와 완전히 같은 형식으로
서명하므로(같은 JWT_SECRET/JWT_ALGORITHM을 공유하는 같은 인프라), 별도 서비스 계정을
DB에 만들 필요 없이 그대로 Authorization 헤더에 실어 보낼 수 있다.

sub을 실제 관리자 uid가 아니라 "discord-bot"으로 못박아두는 이유: approve_request()가
admin_uid를 approved_by에 그대로 기록하므로, 실제 관리자 계정을 사칭하지 않고 "봇을 통해
승인됨"이 감사 기록에 정직하게 남게 하기 위함이다."""

import os
import datetime

import jwt

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")


def mint_admin_token() -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": "discord-bot",
        "name": "Discord Bot",
        "role": "admin",
        "exp": now + datetime.timedelta(minutes=5),
        "iat": now,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
