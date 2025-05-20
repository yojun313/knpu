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
from rich.text import Text
from upload import upload_file

console = Console()


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
    exe_name = f"BIGMACLAB_MANAGER_{version}"

    # Create a new spec file with the updated name
    new_spec_file = os.path.join(
        output_directory, f"BIGMACLAB_MANAGER_{version}.spec")
    create_spec_file(spec_file, new_spec_file, exe_name)

    try:
        # Run pyinstaller with the new spec file
        venv_python = os.path.join(
            'C:/GitHub/BIGMACLAB/venv', 'Scripts', 'python.exe')  # 가상환경 안의 python

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
    if socket.gethostname() == "BigMacServer":
        output_directory = "D:/BIGMACLAB/MANAGER/exe"
    else:
        output_directory = "./build_output"

    spec_file = os.path.join(os.path.dirname(__file__), 'build.spec')
    iss_path = os.path.join(os.path.dirname(__file__), 'setup.iss')

    while True:
        console.rule("[bold green]🚀 BIGMACLAB MANAGER 빌드 시스템 시작")
        version = input("📦 Enter the program version ('r'=reuse, 'n'=next): ")

        if version == 'r':
            version = currentVersion
        elif version == 'n':
            current = Version(currentVersion)
            next_version = Version(
                f"{current.major}.{current.minor}.{current.micro + 1}")
            version = str(next_version)

        same_version_path = os.path.join(
            output_directory, f"BIGMACLAB_MANAGER_{version}")
        if os.path.exists(same_version_path):
            shutil.rmtree(same_version_path)
            console.print(f"[yellow]⚠️ 이전 동일 버전({version}) 디렉토리 삭제됨")

        # Build
        console.print(
            Panel.fit(f"[bold cyan]📦 빌드 시작: MANAGER {version}", title="PyInstaller"))
        build_exe_from_spec(spec_file, output_directory, version)
        console.print("[green]✅ 빌드 완료")

        # Time log
        now = datetime.now()
        current_time = now.strftime("%Y-%m-%d %H:%M")
        currentVersion = version
        console.print(
            Panel.fit(f"[bold green]🕒 {current_time}\n빌드 완료: BIGMACLAB_MANAGER_{version}"))

        # Inno Setup update
        console.print(
            Panel.fit(f"[bold magenta]⚙️ Inno Setup 버전 정보 업데이트", title="setup.iss 처리"))
        with open(iss_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        updated_lines = []
        pattern = r'^#define\s+MyAppVersion\s+"[\d.]+"'
        for line in lines:
            if re.match(pattern, line):
                new_line = f'#define MyAppVersion "{version}"\n'
                console.print(
                    f"[cyan]🔁 버전 변경: [white]{line.strip()} → [green]{new_line.strip()}")
                updated_lines.append(new_line)
            else:
                updated_lines.append(line)

        # Temp ISS 실행
        temp_iss_path = os.path.join(
            os.path.dirname(__file__), 'setup_temp.iss')
        with open(temp_iss_path, 'w', encoding='utf-8') as f:
            f.writelines(updated_lines)

        console.print("[bold cyan]📦 Inno Setup 실행 중...")
        subprocess.run(
            [r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe", temp_iss_path])
        os.remove(temp_iss_path)
        console.print("[green]✅ Inno Setup 완료 및 임시 파일 삭제")

        # Upload
        exe_path = os.path.join(
            output_directory, f"BIGMACLAB_MANAGER_{version}", f"BIGMACLAB_MANAGER_{version}.exe")
        console.print(
            Panel.fit(f"[bold blue]☁️ Uploading {exe_path}", title="파일 업로드"))
        upload_file(exe_path)
        console.print("[green]✅ 업로드 완료")

        console.rule("[bold green]🎉 모든 작업 완료")
