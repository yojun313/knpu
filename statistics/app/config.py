"""
0: local
1: production
"""

import os
from dotenv import load_dotenv

load_dotenv()

mode = int(os.getenv("MODE", 1))

if mode == 0:
    STATISTICS_VIEWER_URL = "https://dev-statistics.knpu.re.kr"
else:
    STATISTICS_VIEWER_URL = "https://statistics.knpu.re.kr"
