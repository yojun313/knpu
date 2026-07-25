"""
0: local
1: production
"""

import os
from dotenv import load_dotenv

load_dotenv()

mode = int(os.getenv("MODE"))

if mode == 0:
    NETWORK_VIEWER_URL = "http://localhost:8001"
    KEMKIM_VIEWER_URL = "http://localhost:8008"
    STATISTICS_VIEWER_URL = "http://localhost:8009"
else:
    NETWORK_VIEWER_URL = "https://network.knpu.re.kr"
    KEMKIM_VIEWER_URL = "https://kemkim.knpu.re.kr"
    STATISTICS_VIEWER_URL = "https://statistics.knpu.re.kr"
