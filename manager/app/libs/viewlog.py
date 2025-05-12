from pymongo import MongoClient
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

client = MongoClient(os.getenv("MONGO_URI"))
db = client["manager"]
user_logs = db["user-logs"]
users = db["users"]
console = Console()


def get_username(uid):
    user = users.find_one({"uid": uid})
    return user.get("name", "Unknown") if user else "Unknown"


def is_valid_date(date_string):
    try:
        datetime.strptime(date_string, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def display_user_logs():
    while True:
        documents = list(user_logs.find())

        if not documents:
            console.print("[red]로그 데이터가 없습니다.[/]")
            return

        # 유저 목록 출력
        console.print("\n[bold blue]유저를 선택하세요 ('q' 입력 시 종료):[/bold blue]")
        for i, doc in enumerate(documents):
            name = get_username(doc.get("uid"))
            console.print(f"[{i}] 👤 {name}")

        user_input = Prompt.ask("\n숫자로 유저 선택", default="q")

        if user_input.lower() in ["q", "quit", "exit"]:
            console.print("\n[bold red]종료합니다.[/bold red]")
            break

        if not user_input.isdigit() or int(user_input) not in range(len(documents)):
            console.print("[red]유효한 숫자를 입력하세요.[/red]")
            continue

        selected_doc = documents[int(user_input)]
        uid = selected_doc.get("uid")
        username = get_username(uid)

        console.print(Panel(f"[bold cyan]👤 {username}[/]", title="User", expand=False))

        # 날짜 키 필터링
        date_keys = [key for key in selected_doc.keys() if key not in ["_id", "uid"]]
        date_keys = [key for key in date_keys if is_valid_date(key)]

        if not date_keys:
            console.print("[yellow]해당 유저의 로그가 없습니다.[/]")
            continue

        # 날짜 목록 출력
        console.print("\n[bold magenta]날짜를 선택하세요 ('q' 입력 시 유저 목록으로 돌아감):[/bold magenta]")
        for i, date in enumerate(date_keys):
            count = len(selected_doc[date])
            console.print(f"[{i}] {date} ({count} 개 로그)")

        date_input = Prompt.ask("\n숫자로 날짜 선택", default="q")

        if date_input.lower() in ["q", "quit", "exit"]:
            continue

        if not date_input.isdigit() or int(date_input) not in range(len(date_keys)):
            console.print("[red]유효한 숫자를 입력하세요.[/red]")
            continue

        selected_date = date_keys[int(date_input)]
        logs = selected_doc[selected_date]

        table = Table(title=f"[bold yellow]{selected_date}[/] 로그", show_lines=True)
        table.add_column("Time", style="green", width=12)
        table.add_column("Message", style="white")

        for log in logs:
            time = log.get("time", "-")
            message = log.get("message", "")
            table.add_row(time, message)

        console.print(table)
        console.rule("[bold blue]다시 유저 선택으로 돌아갑니다[/]")

if __name__ == "__main__":
    display_user_logs()
