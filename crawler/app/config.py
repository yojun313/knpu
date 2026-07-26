import os
from dotenv import load_dotenv
import socket

load_dotenv()

MODE = int(os.getenv("MODE", 1))
PROXY = os.getenv("PROXY", "false").lower() == "true"
CRAWL_DATA_PATH = os.getenv("CRAWLDATA_PATH", "./crawldata")
CRAWL_LOG_PATH = os.getenv("CRAWLLOG_PATH", "./crawllog")
CRAWLCOM = socket.gethostname()
MANAGER_SERVER_URL = os.getenv("MANAGER_SERVER_URL", "http://localhost:8000/api")

TRYNUM = 3
SLEEP_TIME = 0
TIMEOUT = 5
MAX_CONCURRENT_JOBS = 1
