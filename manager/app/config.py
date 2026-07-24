import os
from dotenv import load_dotenv

load_dotenv()

VERSION = "3.3.2"

"""
    0: local
    1: production
"""

ASSETS_PATH = os.path.join(os.path.dirname(__file__), "assets")

mode = os.getenv("MODE", None)

if mode is None:
    mode = 1
else:
    mode = int(mode)

# knpu.re.kr 중앙 로그인은 로컬/운영 모드와 무관하게 항상 공개 도메인을 사용한다
# (HOMEPAGE_EDIT_API도 같은 이유로 두 모드 모두 공개 URL을 쓴다)
HOMEPAGE_URL = "https://knpu.re.kr"

if mode == 0:
    MANAGER_SERVER_API = "http://localhost:8000/api"
    MANAGER_PROGRESS_API = "http://localhost:8080"
    HOMEPAGE_EDIT_API = "https://knpu.re.kr/api"
    NETWORK_VIEWER_URL = "http://localhost:8001"
    KEMKIM_VIEWER_URL = "http://localhost:8008"
else:
    MANAGER_SERVER_API = "https://manager.knpu.re.kr/api"
    MANAGER_PROGRESS_API = "https://manager.knpu.re.kr/progress"
    HOMEPAGE_EDIT_API = "https://knpu.re.kr/api"
    NETWORK_VIEWER_URL = "https://network.knpu.re.kr"
    KEMKIM_VIEWER_URL = "https://kemkim.knpu.re.kr"
