import os
from dotenv import load_dotenv

load_dotenv()

VERSION = "3.3.4"

ASSETS_PATH = os.path.join(os.path.dirname(__file__), "assets")

# 데스크톱 클라이언트는 항상 운영 서버에 붙는다. 예전에는 MODE=0일 때 localhost의
# 각 서버로 붙는 로컬 모드가 있었지만, 쓰이지 않아 제거했다.
HOMEPAGE_URL = "https://knpu.re.kr"
HOMEPAGE_EDIT_API = "https://knpu.re.kr/api"
MANAGER_SERVER_API = "https://manager.knpu.re.kr/api"
MANAGER_PROGRESS_API = "https://manager.knpu.re.kr/progress"
NETWORK_VIEWER_URL = "https://network.knpu.re.kr"
KEMKIM_VIEWER_URL = "https://kemkim.knpu.re.kr"
STATISTICS_VIEWER_URL = "https://statistics.knpu.re.kr"
CRAWLER_VIEWER_URL = "https://crawler.knpu.re.kr"

NETWORK_API = f"{NETWORK_VIEWER_URL}/api"
KEMKIM_API = f"{KEMKIM_VIEWER_URL}/api"
STATISTICS_API = f"{STATISTICS_VIEWER_URL}/api"
CRAWLER_API = f"{CRAWLER_VIEWER_URL}/api"
