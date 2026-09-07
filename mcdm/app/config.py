from system.endpoints import public_url

# services.json 의 서비스 키 = 디렉터리 = 'mcdm' (구 'ahp').
# 운영 도메인은 아직 ahp.knpu.re.kr, dev 는 dev.mcdm.knpu.re.kr.
MCDM_BASE_URL = public_url("mcdm")

MCDM_RESPOND_BASE_URL = f"{MCDM_BASE_URL}/r"
