"""MODE
0: dev  (dev*.knpu.re.kr, 18xxx 포트)
1: prod (*.knpu.re.kr, 8xxx 포트)

DB와 계정은 두 모드가 공유한다 — system/db/__init__.py 참고.
"""

import os
from dotenv import load_dotenv

load_dotenv()

MODE = int(os.getenv("MODE", 1))

if MODE == 0:
    AHP_BASE_URL = "https://dev-ahp.knpu.re.kr"
else:
    AHP_BASE_URL = "https://ahp.knpu.re.kr"

# 응답자 배포 링크에 노출되는 공개 베이스 URL(관리자 화면에서 "링크 복사"에 사용)
AHP_RESPOND_BASE_URL = f"{AHP_BASE_URL}/r"
