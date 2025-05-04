from pymongo import MongoClient
import urllib.parse
from dotenv import load_dotenv
import os
from mysql import mySQL

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

crawlList_db = crawler_db["db-list"]
crawlLog_db = crawler_db["log-list"]

user_db = manager_db["users"]
user_logs_db = manager_db["user-logs"]
version_board_db = manager_db["version-board"]
bug_board_db = manager_db["bug-board"]
free_board_db = manager_db["free-board"]
auth_db = manager_db["auth"]

mysql_db = mySQL(os.getenv("MYSQL_HOST"), os.getenv("MYSQL_USER"), os.getenv("MYSQL_PW"), os.getenv("MYSQL_PORT"))