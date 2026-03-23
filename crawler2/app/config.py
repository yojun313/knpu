import os
from dotenv import load_dotenv
import socket   

load_dotenv()

PROXY = os.getenv('PROXY', 'false').lower() == 'true'
CRAWL_DATA_PATH = os.getenv('CRAWLDATA_PATH', './crawldata')
CRAWL_LOG_PATH = os.getenv('CRAWLLOG_PATH', './crawllog')
API_URL = os.getenv('API_URL', 'http://localhost:8000/api')
CRAWLCOM = socket.gethostname()

TRYNUM = 3
SLEEP_TIME = 1
TIMEOUT = 300
