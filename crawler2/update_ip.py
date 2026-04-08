import os
import socket
import requests
from pymongo import MongoClient
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

load_dotenv()

# MongoDB 설정
SSH_HOST = os.getenv("SSH_HOST")
SSH_PORT = int(os.getenv("SSH_PORT", 22))
SSH_USER = os.getenv("SSH_USER")
SSH_KEY  = os.getenv("SSH_KEY")

MONGO_HOST     = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT     = int(os.getenv("MONGO_PORT", 27017))
MONGO_USER     = os.getenv("MONGO_USER")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD")
MONGO_AUTH_DB  = os.getenv("MONGO_AUTH_DB", "admin")

# 크롤러 서버 설정
CRAWLER_SERVER_URL = os.getenv("CRAWLER_SERVER_URL", "http://localhost:3005")
INTERNAL_API_KEY   = os.getenv("INTERNAL_API_KEY")

# 프록시 파일 경로
PROXY_FILE_PATH = os.getenv("PROXY_FILE_PATH")

console = Console()


def connect_mongo() -> MongoClient:
    hostname  = socket.gethostname()
    is_server = "knpu" in hostname or "server" in hostname

    if is_server:
        return MongoClient(
            f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}"
            f"@localhost:{MONGO_PORT}/?authSource={MONGO_AUTH_DB}"
        )
    else:
        import warnings
        warnings.filterwarnings("ignore", module="paramiko")
        from sshtunnel import SSHTunnelForwarder
        tunnel = SSHTunnelForwarder(
            (SSH_HOST, SSH_PORT),
            ssh_username=SSH_USER,
            ssh_pkey=SSH_KEY,
            remote_bind_address=(MONGO_HOST, MONGO_PORT),
            set_keepalive=30,
        )
        tunnel.start()
        return MongoClient(
            f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}"
            f"@127.0.0.1:{tunnel.local_bind_port}/?authSource={MONGO_AUTH_DB}"
        )


def read_proxy_file(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def main():
    if not PROXY_FILE_PATH:
        console.print("[bold red]PROXY_FILE_PATH 환경변수가 설정되지 않았습니다.[/bold red]")
        return

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        transient=True,
        console=console,
    )

    with progress:
        # 1. 프록시 파일 읽기
        task = progress.add_task("프록시 파일 읽는 중...", total=None)
        proxy_list = read_proxy_file(PROXY_FILE_PATH)
        progress.update(task, description=f"프록시 파일 로드 완료 ({len(proxy_list)}개)")
        progress.stop_task(task)

        # 2. MongoDB 연결
        task = progress.add_task("MongoDB 연결 중...", total=None)
        client = connect_mongo()
        collection = client["crawler"]["ip-list"]
        progress.update(task, description="MongoDB 연결 완료")
        progress.stop_task(task)

        # 3. MongoDB 업데이트
        task = progress.add_task("MongoDB 업데이트 중...", total=None)
        collection.update_one(
            {"_id": "proxy_list"},
            {"$set": {"list": proxy_list}},
            upsert=True,
        )
        progress.update(task, description="MongoDB 업데이트 완료")
        progress.stop_task(task)

        # 4. 크롤러 서버에 프록시 재로드 요청
        task = progress.add_task("크롤러 서버 프록시 갱신 중...", total=None)
        try:
            res = requests.post(
                f"{CRAWLER_SERVER_URL}/api/proxy/reload",
                headers={"X-Internal-Key": INTERNAL_API_KEY or ""},
                timeout=10,
            )
            res.raise_for_status()
            data = res.json()
            progress.update(task, description=f"서버 프록시 갱신 완료 ({data.get('count', '?')}개)")
        except Exception as e:
            progress.update(task, description=f"서버 갱신 실패: {e}")
        progress.stop_task(task)

    console.print("[bold green]프록시 업데이트 완료![/bold green]")


if __name__ == "__main__":
    main()
