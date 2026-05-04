import os
import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

load_dotenv()

# 설정
CRAWLER_SERVER_URL = os.getenv("CRAWLER_SERVER_URL", "http://localhost:3001")
INTERNAL_API_KEY   = os.getenv("INTERNAL_API_KEY")
PROXY_FILE_PATH    = os.getenv("PROXY_FILE_PATH")

console = Console()

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
        task = progress.add_task("프록시 파일 읽는 중...", total=None)
        proxy_list = read_proxy_file(PROXY_FILE_PATH)
        progress.update(task, description=f"프록시 파일 로드 완료 ({len(proxy_list)}개)")

        progress.update(task, description="서버로 프록시 리스트 전송 중...")
        try:
            res = requests.post(
                f"{CRAWLER_SERVER_URL}/api/proxy/update",
                headers={"X-Internal-Key": INTERNAL_API_KEY or ""},
                json={"proxies": proxy_list}, # JSON 바디에 리스트 포함
                timeout=15,
            )
            res.raise_for_status()
            data = res.json()
            progress.update(task, description=f"서버 업데이트 완료 ({data.get('count', '?')}개)")
        except Exception as e:
            console.print(f"\n[bold red]서버 통신 실패:[/bold red] {e}")
            return

    console.print("[bold green]프록시 업데이트 프로세스 완료![/bold green]")

if __name__ == "__main__":
    main()