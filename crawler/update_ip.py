from Package.ToolModule import ToolModule
from pymongo import MongoClient
import os
from dotenv import load_dotenv
import urllib.parse
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print

# 초기 설정
console = Console()
load_dotenv()
ToolModule_obj = ToolModule()
pathfinder_obj = ToolModule_obj.pathFinder()

# rich progress spinner
progress = Progress(
    SpinnerColumn(),
    TextColumn("[bold blue]{task.description}"),
    transient=True,
    console=console
)

with progress:
    # 프록시 로딩
    task = progress.add_task("📄 프록시 리스트 불러오는 중...", total=None)
    proxy_path = os.path.join(pathfinder_obj['crawler_folder_path'], '아이피샵(유동프록시).txt')
    proxy_list = ToolModule_obj.read_txt(proxy_path)
    progress.update(task, description="✅ 프록시 리스트 로드 완료")
    progress.stop_task(task)

    # MongoDB 연결
    task = progress.add_task("🔌 MongoDB 연결 중...", total=None)
    username = os.getenv("MONGO_USER")
    password = urllib.parse.quote_plus(os.getenv("MONGO_PW"))
    host = os.getenv("MONGO_HOST")
    port = os.getenv("MONGO_PORT")
    auth_db = os.getenv("MONGO_AUTH_DB")

    uri = f"mongodb://{username}:{password}@{host}:{port}/{auth_db}"
    client = MongoClient(uri)
    crawler_db = client["crawler"]
    collection = crawler_db["ip-list"]
    progress.update(task, description="✅ MongoDB 연결 완료")
    progress.stop_task(task)

    # 프록시 업로드
    task = progress.add_task("☁️ MongoDB에 프록시 리스트 업로드 중...", total=None)
    collection.update_one(
        {"_id": "proxy_list"},
        {"$set": {"list": proxy_list}},
        upsert=True
    )
    progress.update(task, description="✅ MongoDB 업데이트 완료")
    progress.stop_task(task)

# 최종 메시지
console.print("[bold green]🎉 프록시 리스트 MongoDB 업데이트 완료![/bold green]")
