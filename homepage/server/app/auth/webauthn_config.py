import os

MODE = int(os.getenv("MODE", 1))

RP_ID = "knpu.re.kr"
RP_NAME = "KNPU FPEI"

BASE_URL = "https://dev.knpu.re.kr" if MODE == 0 else "https://knpu.re.kr"

# WebAuthn 검증은 dev/prod 어느 쪽에서 등록/로그인해도 통과해야 하므로 둘 다 허용한다.
EXPECTED_ORIGINS = ["https://knpu.re.kr", "https://dev.knpu.re.kr"]

CHALLENGE_TTL_MINUTES = 5
