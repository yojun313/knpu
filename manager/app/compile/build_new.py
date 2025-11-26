import os
import re
import shutil
import socket
import subprocess
from datetime import datetime

from packaging.version import Version
from rich.console import Console
from rich.panel import Panel
import requests

from upload import upload_file

console = Console()

# -------------------------------
# 경로 설정
# -------------------------------
OUTPUT_DIRECTORY = "D:/knpu/MANAGER/exe"

# 이 빌드 스크립트가 있는 디렉토리
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# 프로젝트 루트(여기 기준 상위 폴더에 main.py 있다고 가정)
APP_PATH = os.path.dirname(SCRIPT_DIR)
MAIN_SCRIPT = os.path.join(APP_PATH, "main.py")

# 가상환경 안의 python (여기에서 nuitka 실행)
VENV_PYTHON = os.path.join("C:/GitHub/knpu/venv", "Scripts", "python.exe")

# 기본 버전 (처음 실행 시 기준값, 필요하면 수정)
currentVersion = "1.0.0"


# -------------------------------
# Pushover 알림
# -------------------------------
def sendPushOver(msg, user_key="uvz7oczixno7daxvgxmq65g2gbnsd5", image_path=False):
    app_key_list = ["a22qabchdf25zzkd1vjn12exjytsjx"]

    for app_key in app_key_list:
        try:
            url = "https://api.pushover.net/1/messages.json"
            data = {
                "token": app_key,
                "user": user_key,
                "message": msg,
            }

            if not image_path:
                response = requests.post(url, data=data)
            else:
                with open(image_path, "rb") as f:
                    files = {
                        "attachment": ("image.png", f, "image/png"),
                    }
                    response = requests.post(url, data=data, files=files)

            # 한 번 성공하면 더 돌 필요 없음
            break
        except Exception:
            continue


# -------------------------------
# Inno Setup 버전 문자열 수정
# -------------------------------
def update_inno_version(iss_path: str, new_version: str) -> str:
    """setup.iss 안의 MyAppVersion 값을 new_version으로 바꾸고
    임시 .iss 파일 경로를 반환한다.
    """
    temp_iss_path = os.path.join(os.path.dirname(iss_path), "setup_temp.iss")

    with open(iss_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    updated_lines = []
    # 앞에 공백 허용, 버전 문자열은 알파벳/숫자/점/대시 허용
    pattern = r'^\s*#define\s+MyAppVersion\s+"[\w.\-]+"'

    for line in lines:
        if re.match(pattern, line):
            new_line = f'#define MyAppVersion "{new_version}"\n'
            updated_lines.append(new_line)
            print(f"[INFO] MyAppVersion 변경: {line.strip()} → {new_line.strip()}")
        else:
            updated_lines.append(line)

    with open(temp_iss_path, "w", encoding="utf-8") as f:
        f.writelines(updated_lines)

    return temp_iss_path


# -------------------------------
# Nuitka 빌드 함수
# -------------------------------
def build_exe_with_nuitka(main_script: str, output_directory: str, version: str):
    """
    Nuitka로 MANAGER_{version}.exe 빌드.
    결과물: {OUTPUT_DIRECTORY}/MANAGER_{version}.exe
    """
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    exe_name = f"MANAGER_{version}.exe"

    console.print(
        Panel.fit(
            f"[bold cyan]Nuitka 빌드 시작\n[white]main: {main_script}\n[white]output: {os.path.join(output_directory, exe_name)}",
            title="Nuitka",
        )
    )

    # Nuitka 옵션 구성
    # 필요에 따라 플러그인(예: pyqt5)을 추가
    nuitka_cmd = [
        VENV_PYTHON,
        "-m",
        "nuitka",
        "--standalone",                 
        "--remove-output",
        "--windows-console-mode=disable",
        "--enable-plugin=pyqt6",
        f"--output-dir={output_directory}",
        f"--output-filename=MANAGER_{version}",  
        f"--python-for-scons={VENV_PYTHON}",
        main_script,
    ]

    # 실행
    result = subprocess.run(nuitka_cmd)

    if result.returncode != 0:
        raise RuntimeError(f"Nuitka 빌드 실패 (exit code {result.returncode})")

    console.print(f"[green]✅ Nuitka 빌드 완료: MANAGER_{version}.dist 생성됨")


# -------------------------------
# 메인 루프
# -------------------------------
if __name__ == "__main__":
    output_directory = OUTPUT_DIRECTORY

    # 기존에 쓰던 iss 파일 경로
    iss_path = os.path.join(SCRIPT_DIR, "setup_new.iss")

    while True:
        console.rule("[bold green]MANAGER 빌드 시스템 시작 (Nuitka 버전)")
        version = input("프로그램 버전 입력 ('r'=reuse, 'n'=next): ").strip()

        if version == "r":
            # 이전에 사용한 버전 값 그대로 사용
            version = currentVersion
        elif version == "n":
            # micro 버전만 +1
            current = Version(currentVersion)
            next_version = Version(f"{current.major}.{current.minor}.{current.micro + 1}")
            version = str(next_version)
        else:
            # 사용자가 직접 버전 문자열을 입력한 경우
            # 예: 1.3.5
            pass

        same_version_path = os.path.join(output_directory, f"MANAGER_{version}")
        if os.path.exists(same_version_path):
            shutil.rmtree(same_version_path)
            console.print(f"[yellow]이전 동일 버전({version}) 디렉토리 삭제됨: {same_version_path}")

        # -----------------------
        # Nuitka 빌드
        # -----------------------
        build_exe_with_nuitka(MAIN_SCRIPT, output_directory, version)
        console.print("[green]빌드 완료")

        # 시간 로그
        now = datetime.now()
        current_time = now.strftime("%Y-%m-%d %H:%M")
        currentVersion = version

        console.print(
            Panel.fit(f"[bold green]{current_time}\n빌드 완료: MANAGER_{version}")
        )

        # -----------------------
        # Inno Setup 처리
        # -----------------------
        console.print(
            Panel.fit("[bold magenta]Inno Setup 버전 정보 업데이트", title="setup.iss 처리")
        )

        temp_iss_path = update_inno_version(iss_path, version)

        console.print("[bold cyan]Inno Setup 컴파일 중...")
        subprocess.run(
            [r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe", temp_iss_path],
            check=True,
        )

        os.remove(temp_iss_path)
        console.print("[green]Inno Setup 완료 및 임시 파일 삭제")

        # -----------------------
        # 업로드
        # -----------------------
        dist_folder = os.path.join(output_directory, f"MANAGER_{version}.dist")
        installer_exe = os.path.join(output_directory, f"MANAGER_{version}.exe")
        console.print(
            Panel.fit(f"[bold blue]Uploading {installer_exe}", title="파일 업로드")
        )
        upload_file(installer_exe)
        console.print("[green]업로드 완료")

        console.rule("[bold green]모든 작업 완료")
        sendPushOver(f"MANAGER {version} 빌드 완료\n\n{current_time}")
