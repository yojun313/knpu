"""
0: local
1: production
"""

import os
from dotenv import load_dotenv

load_dotenv()

mode = int(os.getenv("MODE"))

LLM_API_URL = "http://localhost:8000/api"
LLM_KEY = os.getenv("ADMIN_TOKEN")