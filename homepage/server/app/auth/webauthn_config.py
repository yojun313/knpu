import os

# 다른 인증 코드(routes/auth_routes.py의 COOKIE_DOMAIN 등)와 동일하게 MODE로
# 운영/로컬을 나눈다. WebAuthn은 rp_id/origin이 실제 접속 도메인과 정확히 일치해야
# 동작하므로 로컬 개발 환경(MODE=0)은 localhost 기준으로 별도 설정한다.
MODE = int(os.getenv("MODE", 1))

RP_ID = "knpu.re.kr" if MODE == 1 else "localhost"
RP_NAME = "KNPU FPEI"
EXPECTED_ORIGIN = "https://knpu.re.kr" if MODE == 1 else "http://localhost:8002"

CHALLENGE_TTL_MINUTES = 5
