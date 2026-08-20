from system.endpoints import HOMEPAGE_URL, WEBAUTHN_RP_ID, all_origins

RP_ID = WEBAUTHN_RP_ID
RP_NAME = "KNPU FPEI"

# 이 인스턴스가 실제로 서빙되는 주소. 인증 메일의 링크처럼 "지금 이 인스턴스"를
# 가리켜야 하는 곳에 쓴다.
BASE_URL = HOMEPAGE_URL

# 검증은 dev/prod 어느 쪽에서 등록/로그인해도 통과해야 하므로 둘 다 허용한다.
EXPECTED_ORIGINS = all_origins("homepage")

CHALLENGE_TTL_MINUTES = 5
