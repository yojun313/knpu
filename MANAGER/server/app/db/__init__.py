from pymongo import MongoClient
import urllib.parse
from dotenv import load_dotenv
import os

load_dotenv()

username = os.getenv("MONGO_USER")
password = urllib.parse.quote_plus(os.getenv("MONGO_PW"))  # 특수문자 인코딩
host = os.getenv("MONGO_HOST")
port = os.getenv("MONGO_PORT")
auth_db = os.getenv("MONGO_AUTH_DB")

uri = f"mongodb://{username}:{password}@{host}:{port}/{auth_db}"

client = MongoClient(uri)

manager_db = client["manager"]
crawler_db = client["crawler"]

crawlDbList_collection = crawler_db["db_list"]

user_collection = manager_db["users"]
user_settings_collection = manager_db["user-settings"]
user_logs_collection = manager_db["user-logs"]
versionBoard_collection = manager_db["version-board"]
bugBoard_collection = manager_db["bug-board"]
freeBoard_collection = manager_db["free-board"]
auth_collection = manager_db["auth"]
