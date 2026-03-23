import os
from dotenv import load_dotenv
import socket   

load_dotenv()

PROXY = os.getenv('PROXY', 'false').lower() == 'true'
CRAWL_PATH = os.getenv('CRAWL_PATH', './crawl_data')
CRAWL_LOG_PATH = os.getenv('CRAWL_LOG_PATH', './crawl_logs')
API_URL = os.getenv('API_URL', 'http://localhost:8000/api')
CRAWLCOM = socket.gethostname()

TRYNUM = 3
SLEEP_TIME = 1
TIMEOUT = 300
