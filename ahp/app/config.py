"""
0: local
1: production
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
