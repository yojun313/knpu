"""
0: local
1: production
"""

import os
from dotenv import load_dotenv

load_dotenv()

mode = int(os.getenv("MODE", 1))

if mode == 0:
    NETWORK_VIEWER_URL = "https://dev-network.knpu.re.kr"
else:
    NETWORK_VIEWER_URL = "https://network.knpu.re.kr"
