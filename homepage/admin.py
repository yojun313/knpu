import os
import sys
import json
from typing import List, Optional
import tkinter as tk
from tkinter import filedialog
import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich import box
import boto3

# ---------- 환경 변수 & Cloudflare R2 설정 ----------
load_dotenv()  # .env 로부터 ↓ 값들 읽기

# 서버 API 엔드포인트 (원하면 수정)
API_BASE = "https://home.knpu.re.kr/api"
MEMBER_EDIT_URL = f"{API_BASE}/edit/member"
MEMBER_LIST_URL = f"{API_BASE}/members"
NEWS_LIST_URL = f"{API_BASE}/news"
NEWS_EDIT_URL = f"{API_BASE}/edit/news"
PAPER_LIST_URL = f"{API_BASE}/papers"
PAPER_EDIT_URL = f"{API_BASE}/edit/paper"
MEMBER_DELETE_URL = f"{API_BASE}/member"
NEWS_DELETE_URL = f"{API_BASE}/news"
PAPER_DELETE_URL = f"{API_BASE}/paper"

LOCAL_TEMP_DIR = "./uploads"  # 업로드 전 임시 복사 폴더
os.makedirs(LOCAL_TEMP_DIR, exist_ok=True)
console = Console()


def upload_image(src_path: str, object_name: Optional[str] = None) -> str:
    """
    src_path 의 파일을 FastAPI 서버의 업로드 엔드포인트를 이용해 업로드 후 public URL 반환
    """
    if not os.path.exists(src_path):
        raise FileNotFoundError(src_path)

    # 서버 업로드 엔드포인트
    UPLOAD_URL = f"{API_BASE}/image"

    # 파일 준비
    with open(src_path, "rb") as f:
        files = {"file": (os.path.basename(src_path), f, "image/jpeg")}
        data = {"folder": "members"}  # 혹은 news/papers 등 호출하는 쪽에서 지정
        headers = {"Authorization": f"Bearer {os.getenv('ADMIN_TOKEN')}"}
        response = requests.post(UPLOAD_URL, files=files, data=data, headers=headers)

    if response.status_code == 200:
        result = response.json()
        return result["url"]  # FastAPI 엔드포인트가 반환한 public URL
    else:
        raise RuntimeError(f"업로드 실패: {response.status_code}, {response.text}")


# ---------- 헬퍼 ----------


def prompt_list(label: str, default: Optional[List[str]] = None) -> List[str]:
    """
    ';' 로 구분된 문자열을 받아 List[str] 로 반환.
    빈 입력이면 default 를 그대로 유지
    """
    default_str = "; ".join(default) if default else ""
    value = Prompt.ask(
        f"{label}  (세미콜론 ; 로 여러 개 입력 / Enter=유지)", default=default_str
    )
    return (
        [x.strip() for x in value.split(";") if x.strip()] if value else (default or [])
    )


def show_object(obj: dict, title="객체"):
    table = Table(title=title, box=box.ROUNDED, title_style="bold green")
    table.add_column("키", style="cyan bold", no_wrap=True)
    table.add_column("값", style="white")

    for k, v in obj.items():
        table.add_row(
            str(k),
            json.dumps(v, ensure_ascii=False)
            if isinstance(v, (list, dict))
            else str(v),
        )
    console.print(table)


def choose_local_file(title="이미지 선택") -> Optional[str]:
    try:
        # 루트 창 생성
        root = tk.Tk()
        # root.withdraw()  # Tk 창 숨기기
        path = filedialog.askopenfilename(
            title=title, filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.webp")]
        )
        root.destroy()
        return path or None
    except Exception as e:
        console.print(f"[red]파일 다이얼로그 오류:[/] {e}")
        return None


# ---------- 멤버/뉴스 CRUD ----------
def upsert_to_server(url: str, payload: dict):
    headers = {"Authorization": f"Bearer {os.getenv('ADMIN_TOKEN')}"}
    res = requests.post(url, headers=headers, json=payload)
    if res.status_code == 200:
        console.print(Panel("✅ 성공적으로 반영되었습니다!", style="bold green"))
        show_object(res.json(), title="서버 응답")
    else:
        console.print(
            Panel(f"❌ 실패 ({res.status_code})\n{res.text}", style="bold red")
        )
        sys.exit(1)


def delete_from_server(url: str, params: dict):
    headers = {"Authorization": f"Bearer {os.getenv('ADMIN_TOKEN')}"}
    res = requests.delete(url, headers=headers, params=params)
    if res.status_code == 200:
        console.print(Panel("✅ 성공적으로 삭제되었습니다!", style="bold green"))
        show_object(res.json() if res.text else {}, title="서버 응답")
    else:
        console.print(
            Panel(f"❌ 실패 ({res.status_code})\n{res.text}", style="bold red")
        )


def fetch_members() -> List[dict]:
    try:
        return requests.get(MEMBER_LIST_URL).json()
    except Exception as e:
        console.print(f"[red]멤버 목록 불러오기 실패:[/] {e}")
        return []


def fetch_news() -> List[dict]:
    try:
        return requests.get(NEWS_LIST_URL).json()
    except Exception as e:
        console.print(f"[red]뉴스 목록 불러오기 실패:[/] {e}")
        return []


def select_member() -> Optional[dict]:
    """수정할 멤버를 선택하고 해당 딕셔너리를 반환"""
    members = fetch_members()
    if not members:
        console.print("[yellow]편집할 멤버가 없습니다.[/]")
        return None

    # 목록 표시
    list_table = Table(title="멤버 목록", box=box.MINIMAL_DOUBLE_HEAD, show_lines=True)
    list_table.add_column("No", justify="right")
    list_table.add_column("이름")
    list_table.add_column("포지션")
    for idx, m in enumerate(members, 1):
        list_table.add_row(str(idx), m["name"], m.get("position", ""))
    console.print(list_table)

    idx = int(
        Prompt.ask(
            "수정할 멤버 번호", choices=[str(i) for i in range(1, len(members) + 1)]
        )
    )
    return members[idx - 1]


def add_or_edit_member(edit: bool = False):
    # ---- 멤버 선택 먼저 ----
    if edit:
        data = select_member()
        if not data:  # 목록이 없거나 선택이 취소된 경우
            return
        console.rule(f"[bold cyan]{data['name']} 수정[/]")
    else:
        data = {}

    # ---- 필드 입력 ----
    def ask(key, default=""):
        return Prompt.ask(f"{key}", default=default).strip()

    # 이미지 처리 (편집 시 기본 False, 신규 추가 시 True)
    if Confirm.ask("프로필 이미지를 새로 선택하시겠습니까?", default=not edit):
        src = choose_local_file()
        if src:
            # 파일명을 이름_확장명으로 변경해 버킷에 저장
            ext = os.path.splitext(src)[1]
            safe_name = data.get("name", "image").replace(" ", "_") or "image"
            object_name = f"members/{ask('저장될 파일명(공백=자동, 영문/숫자만)', default=safe_name)}{ext}"
            # R2 에 업로드 후 URL
            image_url = upload_image(src, object_name)
            data["image"] = image_url

    # 기본 필드
    data["name"] = ask("이름", default=data.get("name", ""))
    data["position"] = ask("포지션", default=data.get("position", ""))
    data["affiliation"] = ask("소속(affiliation)", default=data.get("affiliation", ""))
    data["section"] = ask("구분(section)", default=data.get("section", ""))
    data["email"] = ask("이메일", default=data.get("email", ""))
    data["학력"] = prompt_list("학력", default=data.get("학력", []))
    data["경력"] = prompt_list("경력", default=data.get("경력", []))
    data["연구"] = prompt_list("연구", default=data.get("연구", []))

    show_object(data, title="보낼 데이터")
    if Confirm.ask("서버에 저장할까요?", default=True):
        upsert_to_server(MEMBER_EDIT_URL, data)


def delete_member_ui():
    data = select_member()
    if not data:
        return
    if Confirm.ask(f"{data['name']} 멤버를 삭제할까요?", default=False):
        delete_from_server(MEMBER_DELETE_URL, {"name": data["name"]})


def select_news() -> Optional[dict]:
    """수정할 뉴스를 선택하고 해당 딕셔너리를 반환"""
    news_list = fetch_news()
    if not news_list:
        console.print("[yellow]편집할 뉴스가 없습니다.[/]")
        return None

    # 목록 표시
    list_table = Table(title="뉴스 목록", box=box.MINIMAL_DOUBLE_HEAD, show_lines=True)
    list_table.add_column("No", justify="right")
    list_table.add_column("제목")
    list_table.add_column("날짜")
    for idx, n in enumerate(news_list, 1):
        list_table.add_row(str(idx), n["title"], n.get("date", ""))
    console.print(list_table)

    idx = int(
        Prompt.ask(
            "수정할 뉴스 번호", choices=[str(i) for i in range(1, len(news_list) + 1)]
        )
    )
    return news_list[idx - 1]


def add_or_edit_news(edit: bool = False):
    if edit:
        data = select_news()
        if not data:
            return
        console.rule(f"[bold cyan]{data['title']} 수정[/]")
    else:
        data = {}

    def ask(key, default=""):
        return Prompt.ask(f"{key}", default=default).strip()

    if Confirm.ask("썸네일 이미지를 새로 선택하시겠습니까?", default=not edit):
        src = choose_local_file()
        if src:
            object_name = f"news/{os.path.basename(src)}"
            image_url = upload_image(src, object_name)
            data["image"] = image_url

    data["title"] = ask("제목", default=data.get("title", ""))
    data["content"] = ask("내용", default=data.get("content", ""))
    data["date"] = ask("날짜 (YYYY.MM 또는 YYYY.MM.DD)", default=data.get("date", ""))
    data["url"] = ask("원본 기사 URL", default=data.get("url", ""))

    show_object(data, title="보낼 뉴스 데이터")
    if Confirm.ask("서버에 저장할까요?", default=True):
        upsert_to_server(NEWS_EDIT_URL, data)


def delete_news_ui():
    data = select_news()
    if not data:
        return
    if Confirm.ask(f"{data['title']} 뉴스를 삭제할까요?", default=False):
        delete_from_server(NEWS_DELETE_URL, {"date": data["date"]})


def fetch_papers() -> List[dict]:
    try:
        return requests.get(PAPER_LIST_URL).json()
    except Exception as e:
        console.print(f"[red]논문 목록 불러오기 실패:[/] {e}")
        return []


def select_paper() -> Optional[dict]:
    papers_list = fetch_papers()  # list 형태라고 가정
    if not papers_list:
        console.print("[yellow]편집할 논문이 없습니다.[/]")
        return None

    # 연도를 key로, papers를 value로 변환
    papers_by_year = {str(doc["year"]): doc.get("papers", []) for doc in papers_list}
    years = list(papers_by_year.keys())

    year = Prompt.ask("연도를 선택하세요", choices=years)
    papers = papers_by_year[year]

    list_table = Table(
        title=f"{year}년도 논문 목록", box=box.MINIMAL_DOUBLE_HEAD, show_lines=True
    )
    list_table.add_column("No", justify="right")
    list_table.add_column("제목")
    list_table.add_column("저자들")
    list_table.add_column("컨퍼런스/저널")
    for idx, p in enumerate(papers, 1):
        list_table.add_row(
            str(idx),
            p.get("title", ""),
            ", ".join(p.get("authors", [])),
            p.get("conference", ""),
        )
    console.print(list_table)

    idx = int(
        Prompt.ask(
            "수정할 논문 번호", choices=[str(i) for i in range(1, len(papers) + 1)]
        )
    )
    return papers[idx - 1]


def add_or_edit_paper(edit: bool = False):
    if edit:
        data = select_paper()
        if not data:
            return
        console.rule(f"[bold cyan]{data['title']} 수정[/]")
    else:
        data = {}

    def ask(key, default=""):
        return Prompt.ask(f"{key}", default=default).strip()

    # 연도를 반드시 입력받기
    year = ask("연도 (예: 2024)")

    data["title"] = ask("제목", default=data.get("title", ""))
    data["authors"] = prompt_list("저자들", default=data.get("authors", []))
    data["conference"] = ask("컨퍼런스/저널", default=data.get("conference", ""))
    data["link"] = ask("논문 링크(URL)", default=data.get("link", ""))

    show_object(data, title="보낼 논문 데이터")

    if Confirm.ask("서버에 저장할까요?", default=True):
        # payload에 year를 같이 담아서 보냄
        payload = {
            "year": year,
            "paper": data,
        }
        upsert_to_server(PAPER_EDIT_URL, payload)


def delete_paper_ui():
    papers_list = fetch_papers()
    papers_by_year = {str(doc["year"]): doc.get("papers", []) for doc in papers_list}
    years = list(papers_by_year.keys())
    if not years:
        console.print("[yellow]삭제할 논문이 없습니다.[/]")
        return
    year = Prompt.ask("연도를 선택하세요", choices=years)
    papers = papers_by_year[year]

    list_table = Table(
        title=f"{year}년도 논문 목록", box=box.MINIMAL_DOUBLE_HEAD, show_lines=True
    )
    list_table.add_column("No", justify="right")
    list_table.add_column("제목")
    for idx, p in enumerate(papers, 1):
        list_table.add_row(str(idx), p.get("title", ""))
    console.print(list_table)

    idx = int(
        Prompt.ask(
            "삭제할 논문 번호", choices=[str(i) for i in range(1, len(papers) + 1)]
        )
    )
    title = papers[idx - 1]["title"]

    if Confirm.ask(f"{year}년도의 '{title}' 논문을 삭제할까요?", default=False):
        delete_from_server(PAPER_DELETE_URL, {"year": year, "title": title})


# ---------- 메인 메뉴 ----------


def member_menu():
    while True:
        console.rule("[bold blue]멤버 관리[/]")
        console.print("1) 멤버 추가")
        console.print("2) 멤버 수정")
        console.print("3) 멤버 삭제")
        console.print("0) 뒤로가기")
        choice = Prompt.ask("선택", choices=["1", "2", "3", "0"])

        if choice == "1":
            add_or_edit_member(edit=False)
        elif choice == "2":
            add_or_edit_member(edit=True)
        elif choice == "3":
            delete_member_ui()
        elif choice == "0":
            break


def news_menu():
    while True:
        console.rule("[bold blue]뉴스 관리[/]")
        console.print("1) 뉴스 추가")
        console.print("2) 뉴스 수정")
        console.print("3) 뉴스 삭제")
        console.print("0) 뒤로가기")
        choice = Prompt.ask("선택", choices=["1", "2", "3", "0"])

        if choice == "1":
            add_or_edit_news(edit=False)
        elif choice == "2":
            add_or_edit_news(edit=True)
        elif choice == "3":
            delete_news_ui()
        elif choice == "0":
            break


def paper_menu():
    while True:
        console.rule("[bold blue]논문 관리[/]")
        console.print("1) 논문 추가")
        console.print("2) 논문 수정")
        console.print("3) 논문 삭제")
        console.print("0) 뒤로가기")
        choice = Prompt.ask("선택", choices=["1", "2", "3", "0"])

        if choice == "1":
            add_or_edit_paper(edit=False)
        elif choice == "2":
            add_or_edit_paper(edit=True)
        elif choice == "3":
            delete_paper_ui()
        elif choice == "0":
            break


def main():
    while True:
        console.rule("[bold magenta]LAB CONTENT MANAGER[/]")
        console.print("1) 멤버 관리")
        console.print("2) 뉴스 관리")
        console.print("3) 논문 관리")
        console.print("0) 종료")
        choice = Prompt.ask("선택", choices=["1", "2", "3", "0"])

        if choice == "1":
            member_menu()
        elif choice == "2":
            news_menu()
        elif choice == "3":
            paper_menu()
        elif choice == "0":
            console.print("안녕히 가세요! 👋")
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[bold yellow]사용자 종료[/]")
