from Package.ToolModule import ToolModule
from pymongo import MongoClient
import os
from dotenv import load_dotenv
import urllib.parse

load_dotenv()

ToolModule_obj = ToolModule()
pathfinder_obj = ToolModule_obj.pathFinder()

# 프록시 리스트 로드
proxy_path = os.path.join(pathfinder_obj['crawler_folder_path'], '아이피샵(유동프록시).txt')
proxy_list = ToolModule_obj.read_txt(proxy_path)

# MongoDB 환경변수 로드 및 연결
username = os.getenv("MONGO_USER")
password = urllib.parse.quote_plus(os.getenv("MONGO_PW"))  # 특수문자 인코딩
host = os.getenv("MONGO_HOST")
port = os.getenv("MONGO_PORT")
auth_db = os.getenv("MONGO_AUTH_DB")

uri = f"mongodb://{username}:{password}@{host}:{port}/{auth_db}"
client = MongoClient(uri)

crawler_db = client["crawler"]
collection = crawler_db["ip-list"]

# ✅ 단일 문서로 upsert (기존 문서 덮어쓰기)
collection.update_one(
    {"_id": "proxy_list"},                # 고정 ID 사용
    {"$set": {"list": proxy_list}},       # 내용 업데이트
    upsert=True                           # 없으면 생성
)
