from Package.ToolModule import ToolModule
from pymongo import MongoClient
import os
from dotenv import load_dotenv
from sshtunnel import SSHTunnelForwarder
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
import socket

# 초기 설정
load_dotenv()

SSH_HOST = os.getenv("SSH_HOST")
SSH_PORT = int(os.getenv("SSH_PORT", 22))
SSH_USER = os.getenv("SSH_USER")
SSH_KEY = os.getenv("SSH_KEY")

# MongoDB 설정
MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = int(os.getenv("MONGO_PORT", 27017))
MONGO_USER = os.getenv("MONGO_USER")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD")
MONGO_AUTH_DB = os.getenv("MONGO_AUTH_DB", "admin")

hostname = socket.gethostname()
is_server = ("knpu" in hostname or "server" in hostname)  # 서버 이름 기준으로 판단

if is_server:
    # 서버 내부에서 실행 → 로컬 MongoDB 바로 사용
    client = MongoClient(
        f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}"
        f"@localhost:{MONGO_PORT}/?authSource={MONGO_AUTH_DB}"
    )
else:
    # 외부에서 실행 → SSH 터널 사용
    server = SSHTunnelForwarder(
        (SSH_HOST, SSH_PORT),
        ssh_username=SSH_USER,
        ssh_pkey=SSH_KEY,
        remote_bind_address=(MONGO_HOST, MONGO_PORT)
    )
    server.start()

    client = MongoClient(
        f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}"
        f"@127.0.0.1:{server.local_bind_port}/?authSource={MONGO_AUTH_DB}"
    )

console = Console()

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
    task = progress.add_task("프록시 리스트 불러오는 중...", total=None)
    proxy_path = os.path.join(pathfinder_obj['crawler_folder_path'], '아이피샵(유동프록시).txt')
    proxy_list = ToolModule_obj.read_txt(proxy_path)
    progress.update(task, description="프록시 리스트 로드 완료")
    progress.stop_task(task)

    # MongoDB 연결
    task = progress.add_task("🔌 MongoDB 연결 중...", total=None)
    crawler_db = client["crawler"]
    collection = crawler_db["ip-list"]
    progress.update(task, description="MongoDB 연결 완료")
    progress.stop_task(task)

    # 프록시 업로드
    task = progress.add_task("MongoDB에 프록시 리스트 업로드 중...", total=None)
    collection.update_one(
        {"_id": "proxy_list"},
        {"$set": {"list": proxy_list}},
        upsert=True
    )
    progress.update(task, description="MongoDB 업데이트 완료")
    progress.stop_task(task)

# 최종 메시지
console.print("[bold green]프록시 리스트 MongoDB 업데이트 완료![/bold green]")
