from pymongo import MongoClient
import urllib.parse
from dotenv import load_dotenv
import os
import sys
from .mysql import mySQL

load_dotenv()



uri = os.getenv("MONGO_URI")
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

mysql_db = mySQL(os.getenv("MYSQL_HOST"), os.getenv("MYSQL_USER"), os.getenv("MYSQL_PW"), int(os.getenv("MYSQL_PORT")))