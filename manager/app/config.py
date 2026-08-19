import os
from dotenv import load_dotenv

load_dotenv()

VERSION = "3.3.4"

"""MODE

여기서의 0은 서버 쪽 dev(dev*.knpu.re.kr / 18xxx)가 아니라, 개발자 PC에서 각 서버를
직접 띄워놓고 붙는 "로컬" 모드다 — 그래서 아래 주소가 18xxx가 아니라 localhost의
운영 포트를 가리킨다. 데스크톱 클라이언트라 배포된 dev 환경을 쓸 일이 없다.
    0: local (개발자 PC에서 서버 직접 실행)
    1: production
"""

ASSETS_PATH = os.path.join(os.path.dirname(__file__), "assets")

mode = os.getenv("MODE", None)

if mode is None:
    mode = 1
else:
    mode = int(mode)

HOMEPAGE_URL = "https://knpu.re.kr"

if mode == 0:
    MANAGER_SERVER_API = "http://localhost:8001/api"
    MANAGER_PROGRESS_API = "http://localhost:8006"
    HOMEPAGE_EDIT_API = "https://knpu.re.kr/api"
    NETWORK_VIEWER_URL = "http://localhost:8003"
    KEMKIM_VIEWER_URL = "http://localhost:8008"
    STATISTICS_VIEWER_URL = "http://localhost:8004"
    CRAWLER_VIEWER_URL = "http://localhost:8002"
else:
    MANAGER_SERVER_API = "https://manager.knpu.re.kr/api"
    MANAGER_PROGRESS_API = "https://manager.knpu.re.kr/progress"
    HOMEPAGE_EDIT_API = "https://knpu.re.kr/api"
    NETWORK_VIEWER_URL = "https://network.knpu.re.kr"
    KEMKIM_VIEWER_URL = "https://kemkim.knpu.re.kr"
    STATISTICS_VIEWER_URL = "https://statistics.knpu.re.kr"
    CRAWLER_VIEWER_URL = "https://crawler.knpu.re.kr"

NETWORK_API = f"{NETWORK_VIEWER_URL}/api"
KEMKIM_API = f"{KEMKIM_VIEWER_URL}/api"
STATISTICS_API = f"{STATISTICS_VIEWER_URL}/api"
CRAWLER_API = f"{CRAWLER_VIEWER_URL}/api"
