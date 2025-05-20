import os
import subprocess
import socket
from datetime import datetime
from packaging.version import Version
import shutil
import re

def create_spec_file(original_spec_file, new_spec_file, exe_name):
    with open(original_spec_file, 'r', encoding='utf-8') as file:
        spec_content = file.read()

    spec_content = spec_content.replace('name=\'BIGMACLAB_MANAGER\'', f'name=\'{exe_name}\'')

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
    new_spec_file = os.path.join(output_directory, f"BIGMACLAB_MANAGER_{version}.spec")
    create_spec_file(spec_file, new_spec_file, exe_name)

    try:
        # Run pyinstaller with the new spec file
        venv_python = os.path.join('C:/GitHub/BIGMACLAB/venv', 'Scripts', 'python.exe')  # 가상환경 안의 python

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
            shutil.rmtree(os.path.join(os.path.dirname(new_spec_file), 'build'))
        print(os.path.dirname(new_spec_file))

if __name__ == "__main__":
    if socket.gethostname() == "BigMacServer":
        output_directory = "D:/BIGMACLAB/BIGMACLAB_MANAGER/exe"

    # Spec file path
    spec_file = os.path.join(os.path.dirname(__file__), 'build.spec')

    while True:
        # Get the version from the user
        version = input("Enter the program version: ")

        if version == 'r':
            version = currentVersion
        elif version == 'n':
            current = Version(currentVersion)
            next_version = Version(f"{current.major}.{current.minor}.{current.micro + 1}")
            version = str(next_version)

        same_version = os.path.join(output_directory, f"BIGMACLAB_MANAGER_{version}")
        if os.path.exists(same_version):
            shutil.rmtree(same_version)
            print(f"\n이전 동일 버전({version}) 삭제됨\n")

        build_exe_from_spec(spec_file, output_directory, version)
        os.system("cls")

        now = datetime.now()
        current_time = now.strftime("%Y-%m-%d %H:%M")
        currentVersion = version
        print(f"{current_time} BIGMACLAB_MANAGER_{version} built successfully\n")
        
        
        # inno setup
        
        iss_path = os.path.join(os.path.dirname(__file__), 'setup.iss')
        with open(iss_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        updated_lines = []
        pattern = r'^#define\s+MyAppVersion\s+"[\d.]+"'

        for line in lines:
            if re.match(pattern, line):
                new_line = f'#define MyAppVersion "{version}"\n'
                print(f"🔁 버전 변경: {line.strip()} → {new_line.strip()}")
                updated_lines.append(new_line)
            else:
                updated_lines.append(line)

        temp_iss_path = os.path.join(os.path.dirname(__file__), 'setup_temp.iss')
        with open(temp_iss_path, 'w', encoding='utf-8') as f:
            f.writelines(updated_lines)

        # temp로 생성된 파일을 실행
        subprocess.run([r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe", temp_iss_path])

        # 사용 후 cleanup
        os.remove(temp_iss_path)
            
        from upload import upload_file
        upload_file(f"BIGMACLAB_MANAGER_{version}.exe")

        
        
