import os
import subprocess
import socket
from datetime import datetime
from packaging.version import Version
import shutil
import re
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

OUTPUT_DIRECTORY = "D:/knpu/MANAGER/exe"

def sendPushOver(msg, user_key = 'uvz7oczixno7daxvgxmq65g2gbnsd5', image_path=False):
    app_key_list = ["a22qabchdf25zzkd1vjn12exjytsjx"]

    for app_key in app_key_list:
        try:
            # Pushover API 설정
            url = 'https://api.pushover.net/1/messages.json'
            # 메시지 내용
            message = {
                'token': app_key,
                'user': user_key,
                'message': msg
            }
            # Pushover에 요청을 보냄
            if image_path == False:
                response = requests.post(url, data=message)
            else:
                response = requests.post(url, data=message, files={
                    "attachment": (
                        "image.png", open(image_path, "rb"),
                        "image/png")
                })
            break
        except:
            continue

def update_inno_version(iss_path: str, new_version: str):
    # 임시 파일 경로 생성
    temp_iss_path = os.path.join(os.path.dirname(iss_path), 'setup_temp.iss')

    with open(iss_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    updated_lines = []
    # 앞에 공백이 있어도 매칭되도록 ^\s*
    # 버전 문자열은 숫자, 점, 문자(-, a-z 등)도 허용
    pattern = r'^\s*#define\s+MyAppVersion\s+"[\w.\-]+"'

    for line in lines:
        if re.match(pattern, line):
            new_line = f'#define MyAppVersion "{new_version}"\n'
            updated_lines.append(new_line)
            print(f"[INFO] MyAppVersion 변경: {line.strip()} → {new_line.strip()}")
        else:
            updated_lines.append(line)

    # 임시 파일에 변경된 내용 저장
    with open(temp_iss_path, 'w', encoding='utf-8') as f:
        f.writelines(updated_lines)

    return temp_iss_path  # 임시 파일 경로 반환

def create_spec_file(original_spec_file, new_spec_file, exe_name):
    with open(original_spec_file, 'r', encoding='utf-8') as file:
        spec_content = file.read()

    spec_content = spec_content.replace(
        'name=\'MANAGER\'', f'name=\'{exe_name}\'')

    with open(new_spec_file, 'w') as file:
        file.write(spec_content)


def build_exe_from_spec(spec_file, output_directory, version):
    # Ensure the output directory exists
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    print(f"Building exe for {spec_file}...")

    # Define the output executable name with version
    exe_name = f"MANAGER_{version}"

    # Create a new spec file with the updated name
    new_spec_file = os.path.join(
        output_directory, f"MANAGER_{version}.spec")
    create_spec_file(spec_file, new_spec_file, exe_name)

    try:
        # Run pyinstaller with the new spec file
        venv_python = os.path.join(
            'C:/GitHub/knpu/venv', 'Scripts', 'python.exe')  # 가상환경 안의 python

        subprocess.run([
            venv_python,
            '-m', 'PyInstaller',
            '--distpath', output_directory,
            '--workpath', os.path.join(output_directory, 'build'),
            new_spec_file
        ])
        print(f"Finished building {exe_name}.exe")
    finally:
        # Clean up the new spec file
        if os.path.exists(new_spec_file):
            os.remove(new_spec_file)
            shutil.rmtree(os.path.join(
                os.path.dirname(new_spec_file), 'build'))
        print(os.path.dirname(new_spec_file))


if __name__ == "__main__":
    output_directory = OUTPUT_DIRECTORY

    spec_file = os.path.join(os.path.dirname(__file__), 'build.spec')
    iss_path = os.path.join(os.path.dirname(__file__), 'setup.iss')

    while True:
        console.rule("[bold green]MANAGER 빌드 및 배포 시스템")
        version = input("Enter the program version ('r'=reuse, 'n'=next): ")

        build_start = datetime.now()
         
        if version == 'r':
            version = currentVersion
        elif version == 'n':
            current = Version(currentVersion)
            next_version = Version(
                f"{current.major}.{current.minor}.{current.micro + 1}")
            version = str(next_version)

        same_version_path = os.path.join(
            output_directory, f"MANAGER_{version}")
        if os.path.exists(same_version_path):
            shutil.rmtree(same_version_path)
            console.print(f"[yellow]이전 동일 버전({version}) 디렉토리 삭제됨")

        # Build
        console.print(
            Panel.fit(f"[bold cyan]빌드 시작: MANAGER {version}", title="PyInstaller"))
        build_exe_from_spec(spec_file, output_directory, version)
        console.print("[green]빌드 완료")

        # Time log
        now = datetime.now()
        current_time = now.strftime("%Y-%m-%d %H:%M")
        currentVersion = version
        console.print(
            Panel.fit(f"[bold green]{current_time}\n빌드 완료: MANAGER_{version}"))

        # Inno Setup update
        console.print(Panel.fit(f"[bold magenta]Inno Setup 버전 정보 업데이트", title="setup.iss 처리"))

        # 임시 파일 생성
        temp_iss_path = update_inno_version(iss_path, version)

        console.print("[bold cyan]Inno Setup 실행 중...")
        subprocess.run(
            [r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe", temp_iss_path])

        # 임시 파일 삭제
        os.remove(temp_iss_path)
        console.print("[green]Inno Setup 완료 및 임시 파일 삭제")

        # Upload
        filename = f"MANAGER_{version}.exe"
        console.print(
            Panel.fit(f"[bold blue]Uploading {filename}", title="파일 업로드"))
        upload_file(filename)
        console.print("[green]업로드 완료")

        console.rule("[bold green]컴파일 및 배포 완료")
        
        build_end = datetime.now()
        elapsed = build_end - build_start
        elapsed_min = elapsed.total_seconds() // 60
        elapsed_sec = int(elapsed.total_seconds() % 60)
        
        sendPushOver(f"MANAGER {version} 빌드 완료\n\n소요시간: {int(elapsed_min)}분 {elapsed_sec}초")
        
        
