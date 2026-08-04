import os
from dotenv import load_dotenv

load_dotenv()

VERSION = "3.3.3"

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

HOMEPAGE_URL = "https://knpu.re.kr"

if mode == 0:
    MANAGER_SERVER_API = "http://localhost:8000/api"
    MANAGER_PROGRESS_API = "http://localhost:8080"
    HOMEPAGE_EDIT_API = "https://knpu.re.kr/api"
    NETWORK_VIEWER_URL = "http://localhost:8001"
    KEMKIM_VIEWER_URL = "http://localhost:8008"
    STATISTICS_VIEWER_URL = "http://localhost:8009"
else:
    MANAGER_SERVER_API = "https://manager.knpu.re.kr/api"
    MANAGER_PROGRESS_API = "https://manager.knpu.re.kr/progress"
    HOMEPAGE_EDIT_API = "https://knpu.re.kr/api"
    NETWORK_VIEWER_URL = "https://network.knpu.re.kr"
    KEMKIM_VIEWER_URL = "https://kemkim.knpu.re.kr"
    STATISTICS_VIEWER_URL = "https://statistics.knpu.re.kr"

NETWORK_API = f"{NETWORK_VIEWER_URL}/api"
KEMKIM_API = f"{KEMKIM_VIEWER_URL}/api"
STATISTICS_API = f"{STATISTICS_VIEWER_URL}/api"
