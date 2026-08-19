"""MODE
0: dev  (dev*.knpu.re.kr, 18xxx 포트)
1: prod (*.knpu.re.kr, 8xxx 포트)

DB와 계정은 두 모드가 공유한다 — system/db/__init__.py 참고.
"""

import os
from dotenv import load_dotenv

load_dotenv()

mode = int(os.getenv("MODE", 1))

if mode == 0:
    KEMKIM_VIEWER_URL = "https://dev-kemkim.knpu.re.kr"
else:
    KEMKIM_VIEWER_URL = "https://kemkim.knpu.re.kr"
