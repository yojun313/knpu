"""
0: local
1: production
"""

import os
from dotenv import load_dotenv

load_dotenv()

mode = int(os.getenv("MODE"))

if mode == 0:
    NETWORK_VIEWER_URL = "http://localhost:8020"
else:
    NETWORK_VIEWER_URL = "https://network.knpu.re.kr"
