import os
from dotenv import load_dotenv
import socket

load_dotenv()

MODE = int(os.getenv("MODE", 1))
PROXY = os.getenv("PROXY", "false").lower() == "true"
# 켜두면 크롤링 중 날짜(구간)가 바뀔 때마다 DB(ip-list)에서 IP 리스트를 새로 받아와
# 그 이후 요청부터는 새 리스트에서 프록시를 골라 쓴다. PROXY가 꺼져 있으면 무시된다.
REFRESH_PROXY_DAILY = os.getenv("REFRESH_PROXY_DAILY", "false").lower() == "true"
CRAWL_DATA_PATH = os.getenv("CRAWLDATA_PATH", "./crawldata")
CRAWL_LOG_PATH = os.getenv("CRAWLLOG_PATH", "./crawllog")
CRAWLCOM = socket.gethostname()
MANAGER_SERVER_URL = os.getenv("MANAGER_SERVER_URL", "http://localhost:8000/api")

TRYNUM = 3
SLEEP_TIME = 1
TIMEOUT = 5
MAX_CONCURRENT_JOBS = 1
