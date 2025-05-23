from pymongo import MongoClient
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

client = MongoClient(os.getenv("MONGO_URI"))
db = client["manager"]
user_logs = db["user-logs"]
user_bugs = db["user-bugs"]
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


def manage_user_devices():
    while True:
        documents = list(users.find())

        if not documents:
            console.print("[red]등록된 유저가 없습니다.[/red]")
            return

        console.print("\n[bold blue]유저를 선택하세요 ('q' 입력 시 종료):[/bold blue]")
        for i, doc in enumerate(documents):
            name = doc.get("name", "Unknown")
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
        username = selected_doc.get("name", "Unknown")
        device_list = selected_doc.get("device_list", [])

        while True:
            console.print(f"\n[bold cyan]👤 {username}의 등록된 디바이스 목록:[/bold cyan]")
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
                        users.update_one({"uid": uid}, {"$push": {"device_list": new_device}})
                        device_list.append(new_device)
                        console.print(f"[green]'{new_device}' 디바이스가 추가되었습니다.[/green]")

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
                device_to_remove = device_list[int(del_index)]
                confirm = Confirm.ask(f"정말로 '{device_to_remove}'를 삭제하시겠습니까?")
                if confirm:
                    users.update_one({"uid": uid}, {"$pull": {"device_list": device_to_remove}})
                    device_list.remove(device_to_remove)
                    console.print(f"[green]'{device_to_remove}' 디바이스가 삭제되었습니다.[/green]")

            elif choice.lower() in ["q", "quit", "exit"]:
                break
            else:
                console.print("[red]유효한 선택지를 입력하세요.[/red]")


def display_user_logs():
    while True:
        documents = list(user_logs.find())

        if not documents:
            console.print("[red]로그 데이터가 없습니다.[/]")
            return

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

       
        date_keys = [key for key in selected_doc.keys() if key not in ["_id", "uid"]]
        date_keys = [key for key in date_keys if is_valid_date(key)]

        if not date_keys:
            console.print("[yellow]해당 유저의 로그가 없습니다.[/]")
            continue

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


def display_user_bug_reports():
    while True:
        documents = list(user_bugs.find())

        if not documents:
            console.print("[red]버그 리포트 데이터가 없습니다.[/]")
            return

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

        date_keys = [key for key in selected_doc.keys() if key not in ["_id", "uid"]]
        date_keys = [key for key in date_keys if is_valid_date(key)]

        if not date_keys:
            console.print("[yellow]해당 유저의 버그 리포트가 없습니다.[/]")
            continue

        console.print("\n[bold magenta]날짜를 선택하세요 ('q' 입력 시 유저 목록으로 돌아감):[/bold magenta]")
        for i, date in enumerate(date_keys):
            count = len(selected_doc[date])
            console.print(f"[{i}] {date} ({count} 개 버그)")

        date_input = Prompt.ask("\n숫자로 날짜 선택", default="q")

        if date_input.lower() in ["q", "quit", "exit"]:
            continue

        if not date_input.isdigit() or int(date_input) not in range(len(date_keys)):
            console.print("[red]유효한 숫자를 입력하세요.[/red]")
            continue

        selected_date = date_keys[int(date_input)]
        bugs = selected_doc[selected_date]

        table = Table(title=f"[bold yellow]{selected_date}[/] 버그 리포트", show_lines=True)
        table.add_column("Time", style="green", width=12)
        table.add_column("Message", style="white")

        for bug in bugs:
            time = bug.get("time", "-")
            message = bug.get("message", "")
            table.add_row(time, message)

        console.print(table)
        console.rule("[bold blue]다시 유저 선택으로 돌아갑니다[/]")


if __name__ == "__main__":
    while True:
        console.print("\n[bold green]메인 메뉴를 선택하세요:[/bold green]")
        console.print("[1] 유저 로그 조회")
        console.print("[2] 유저 버그 리포트 조회")
        console.print("[3] 유저 디바이스 관리")

        choice = Prompt.ask("선택")

        if choice == "1":
            display_user_logs()
        elif choice == "2":
            display_user_bug_reports()
        elif choice == "3":
            manage_user_devices()
        elif choice.lower() in ["q", "quit", "exit"]:
            console.print("[red]프로그램을 종료합니다.[/red]")
            break
        else:
            console.print("[red]유효한 입력이 아닙니다.[/red]")
