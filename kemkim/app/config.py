"""
0: local
1: production
"""

import os
from dotenv import load_dotenv

load_dotenv()

mode = int(os.getenv("MODE", 1))

if mode == 0:
    KEMKIM_VIEWER_URL = "http://localhost:8008"
else:
    KEMKIM_VIEWER_URL = "https://kemkim.knpu.re.kr"
