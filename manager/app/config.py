import os
from dotenv import load_dotenv

load_dotenv()

VERSION = "3.2.5"

"""
    0: local
    1: production
"""

ASSETS_PATH = os.path.join(os.path.dirname(__file__), "assets")
ADMIN_PASSWORD = "$2b$12$y92zRYAOVwDC0UCXnuG5ZuiJXxiT.drxRFVBu4HoYKmDMB.e.y5kq"

mode = os.getenv("MODE", None)

if mode is None:
    mode = 1
else:
    mode = int(mode)

if mode == 0:
    MANAGER_SERVER_API = "http://localhost:8000/api"
    MANAGER_PROGRESS_API = "http://localhost:8080"
    HOMEPAGE_EDIT_API = "https://home.knpu.re.kr/api"
else:
    MANAGER_SERVER_API = "https://manager.knpu.re.kr/api"
    MANAGER_PROGRESS_API = "https://manager-progress.knpu.re.kr"
    HOMEPAGE_EDIT_API = "https://home.knpu.re.kr/api"
