import os
from dotenv import load_dotenv
import socket   

load_dotenv()

MODE = int(os.getenv('MODE', 1)) #0: 개발, 1: 운영
PROXY = os.getenv('PROXY', 'false').lower() == 'true'
CRAWL_DATA_PATH = os.getenv('CRAWLDATA_PATH', './crawldata')
CRAWL_LOG_PATH = os.getenv('CRAWLLOG_PATH', './crawllog')
# API_URL은 더 이상 사용하지 않음 (crawler2가 MongoDB에 직접 접근)
# API_URL = os.getenv('API_URL', 'http://localhost:8000/api')
CRAWLCOM = socket.gethostname()

TRYNUM = 3
SLEEP_TIME = 1
TIMEOUT = 300
MAX_CONCURRENT_JOBS = 1