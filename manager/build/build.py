import os
import subprocess
import socket
from datetime import datetime
from packaging.version import Version
import shutil

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
