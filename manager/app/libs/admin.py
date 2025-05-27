from pymongo import MongoClient
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich import box
from datetime import datetime
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Set timezone (KST)
try:
    import pytz
    KST = pytz.timezone("Asia/Seoul")
except ModuleNotFoundError:
    KST = None

# MongoDB setup
client = MongoClient(os.getenv("MONGO_URI"))
db = client["manager"]
user_logs = db["user-logs"]
user_bugs = db["user-bugs"]
users = db["users"]
console = Console()

# ──────────────────────────── Utilities ─────────────────────────────


def get_username(uid):
    user = users.find_one({"uid": uid})
    return user.get("name", "Unknown") if user else "Unknown"


def is_valid_date(date_string):
    try:
        datetime.strptime(date_string, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def get_today_str():
    return datetime.now(KST).strftime("%Y-%m-%d") if KST else datetime.now().strftime("%Y-%m-%d")

# ────────────────────── Shared Display Function ─────────────────────


def display_logs(documents, date_str, title):
    if not documents:
        console.print(f"[yellow]{date_str}에 대한 {title} 데이터가 없습니다.[/]")
        return

    for doc in documents:
        uid = doc.get("uid")
        username = get_username(uid)
        if username == 'admin':
            continue
        logs = doc.get(date_str, [])

        panel_title = f"👤 {username}"
        table = Table(
            title=f"[bold yellow]{date_str}[/] {title} 로그", show_lines=True, box=box.SIMPLE)
        table.add_column("Time", style="bold green", width=12)
        table.add_column("Message", style="white")

        for log in logs:
            table.add_row(log.get("time", "-"), log.get("message", ""))

        console.print(Panel(table, title=panel_title, title_align="left"))

    console.rule("[bold blue]메인 메뉴로 돌아갑니다[/]")

# ────────────────────── Display Functions ───────────────────────────


def display_user_logs():
    documents = list(user_logs.find())
    if not documents:
        console.print("[red]로그 데이터가 없습니다.[/]")
        return

    while True:
        console.print("\n[bold blue]유저를 선택하세요 ('q' 입력 시 종료):[/bold blue]")
        for i, doc in enumerate(documents):
            console.print(f"[{i}] 👤 {get_username(doc.get('uid'))}")

        user_input = Prompt.ask("\n숫자로 유저 선택", default="q")
        if user_input.lower() in ["q", "quit", "exit"]:
            break
        if not user_input.isdigit() or int(user_input) not in range(len(documents)):
            console.print("[red]유효한 숫자를 입력하세요.[/red]")
            continue

        doc = documents[int(user_input)]
        uid = doc.get("uid")
        username = get_username(uid)

        date_keys = [k for k in doc if is_valid_date(k)]
        if not date_keys:
            console.print("[yellow]해당 유저의 로그가 없습니다.[/]")
            continue

        console.print(
            "\n[bold magenta]날짜를 선택하세요 ('q' 입력 시 유저 목록으로 돌아감):[/bold magenta]")
        for i, date in enumerate(date_keys):
            console.print(f"[{i}] {date} ({len(doc[date])} 개 로그)")

        date_input = Prompt.ask("\n숫자로 날짜 선택", default="q")
        if date_input.lower() in ["q", "quit", "exit"]:
            continue
        if not date_input.isdigit() or int(date_input) not in range(len(date_keys)):
            console.print("[red]유효한 숫자를 입력하세요.[/red]")
            continue

        display_logs([doc], date_keys[int(date_input)], "유저")


def display_user_bug_reports():
    documents = list(user_bugs.find())
    if not documents:
        console.print("[red]버그 리포트 데이터가 없습니다.[/]")
        return

    while True:
        console.print("\n[bold blue]유저를 선택하세요 ('q' 입력 시 종료):[/bold blue]")
        for i, doc in enumerate(documents):
            console.print(f"[{i}] 👤 {get_username(doc.get('uid'))}")

        user_input = Prompt.ask("\n숫자로 유저 선택", default="q")
        if user_input.lower() in ["q", "quit", "exit"]:
            break
        if not user_input.isdigit() or int(user_input) not in range(len(documents)):
            console.print("[red]유효한 숫자를 입력하세요.[/red]")
            continue

        doc = documents[int(user_input)]
        date_keys = [k for k in doc if is_valid_date(k)]
        if not date_keys:
            console.print("[yellow]해당 유저의 버그 리포트가 없습니다.[/]")
            continue

        console.print(
            "\n[bold magenta]날짜를 선택하세요 ('q' 입력 시 유저 목록으로 돌아감):[/bold magenta]")
        for i, date in enumerate(date_keys):
            console.print(f"[{i}] {date} ({len(doc[date])} 개 버그)")

        date_input = Prompt.ask("\n숫자로 날짜 선택", default="q")
        if date_input.lower() in ["q", "quit", "exit"]:
            continue
        if not date_input.isdigit() or int(date_input) not in range(len(date_keys)):
            console.print("[red]유효한 숫자를 입력하세요.[/red]")
            continue

        display_logs([doc], date_keys[int(date_input)], "버그")


def display_logs_by_date():
    while True:
        today = get_today_str()
        date_input = Prompt.ask(
            f"\n조회할 날짜 입력 (기본값 {today}, 'q' → 종료)", default=today)
        if date_input.lower() in ["q", "quit", "exit"]:
            break
        if not is_valid_date(date_input):
            console.print("[red]유효한 날짜 형식이 아닙니다. (YYYY-MM-DD)[/red]")
            continue
        display_logs(
            list(user_logs.find({date_input: {"$exists": True}})), date_input, "유저")


def display_todays_logs():
    today = get_today_str()
    display_logs(list(user_logs.find({today: {"$exists": True}})), today, "유저")


def manage_user_devices():
    documents = list(users.find())
    if not documents:
        console.print("[red]등록된 유저가 없습니다.[/red]")
        return

    while True:
        console.print("\n[bold blue]유저를 선택하세요 ('q' 입력 시 종료):[/bold blue]")
        for i, doc in enumerate(documents):
            console.print(f"[{i}] 👤 {doc.get('name', 'Unknown')}")

        user_input = Prompt.ask("\n숫자로 유저 선택", default="q")
        if user_input.lower() in ["q", "quit", "exit"]:
            break
        if not user_input.isdigit() or int(user_input) not in range(len(documents)):
            console.print("[red]유효한 숫자를 입력하세요.[/red]")
            continue

        doc = documents[int(user_input)]
        uid = doc.get("uid")
        username = doc.get("name", "Unknown")
        device_list = doc.get("device_list", [])

        while True:
            console.print(f"\n[bold cyan]👤 {username}의 디바이스 목록:[/bold cyan]")
            if not device_list:
                console.print("[yellow]등록된 디바이스가 없습니다.[/yellow]")
            else:
                for i, device in enumerate(device_list):
                    console.print(f"[{i}] {device}")

            console.print("\n[bold green]작업을 선택하세요:[/bold green]")
            console.print("[1] 디바이스 추가")
            console.print("[2] 디바이스 삭제")
            console.print("[q] 유저 목록으로 돌아가기")

            choice = Prompt.ask("선택")

            if choice == "1":
                new_device = Prompt.ask("추가할 디바이스 이름")
                if new_device:
                    if new_device in device_list:
                        console.print("[yellow]이미 등록된 디바이스입니다.[/yellow]")
                    else:
                        users.update_one(
                            {"uid": uid}, {"$push": {"device_list": new_device}})
                        device_list.append(new_device)
                        console.print(
                            f"[green]'{new_device}' 디바이스가 추가되었습니다.[/green]")

            elif choice == "2":
                if not device_list:
                    console.print("[red]삭제할 디바이스가 없습니다.[/red]")
                    continue
                del_index = Prompt.ask("삭제할 디바이스 번호", default="q")
                if del_index.lower() in ["q", "quit"]:
                    continue
                if not del_index.isdigit() or int(del_index) not in range(len(device_list)):
                    console.print("[red]유효한 번호를 입력하세요.[/red]")
                    continue
                device = device_list[int(del_index)]
                if Confirm.ask(f"정말로 '{device}'를 삭제하시겠습니까?"):
                    users.update_one(
                        {"uid": uid}, {"$pull": {"device_list": device}})
                    device_list.remove(device)
                    console.print(f"[green]'{device}' 디바이스가 삭제되었습니다.[/green]")

            elif choice.lower() in ["q", "quit", "exit"]:
                break
            else:
                console.print("[red]유효한 선택지를 입력하세요.[/red]")


# ──────────────────────── Main Menu ─────────────────────────────
if __name__ == "__main__":
    while True:
        console.print("\n[bold green]메인 메뉴를 선택하세요:[/bold green]")
        console.print("[1] 유저 로그 조회")
        console.print("[2] 유저 버그 리포트 조회")
        console.print("[3] 유저 디바이스 관리")
        console.print("[4] 날짜별 로그 조회")
        console.print("[5] 오늘 로그 조회")

        choice = Prompt.ask("선택")

        if choice == "1":
            display_user_logs()
        elif choice == "2":
            display_user_bug_reports()
        elif choice == "3":
            manage_user_devices()
        elif choice == "4":
            display_logs_by_date()
        elif choice == "5":
            display_todays_logs()
        else:
            console.print("[red]유효한 입력이 아닙니다.[/red]")
