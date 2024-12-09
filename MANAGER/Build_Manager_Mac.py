import os
import shutil
import subprocess
import socket
from datetime import datetime

def create_setup_py(output_directory, app_name, version, script_path):
    """Creates a setup.py file for py2app."""
    setup_content = f"""
from setuptools import setup

APP = ['{script_path}']
DATA_FILES = []
OPTIONS = {{
    'argv_emulation': True,
    'iconfile': None,
    'plist': {{
        'CFBundleName': '{app_name}',
        'CFBundleShortVersionString': '{version}',
        'CFBundleVersion': '{version}',
        'CFBundleIdentifier': 'com.bigmaclab.{app_name.lower()}',
    }},
}}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={{'py2app': OPTIONS}},
    setup_requires=['py2app'],
)
"""
    setup_py_path = os.path.join(output_directory, "setup.py")
    with open(setup_py_path, "w") as f:
        f.write(setup_content)
    return setup_py_path

def build_dmg(output_directory, version, script_path):
    # Ensure the output directory exists
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    print(f"Building dmg for {script_path}...")

    # Define the app name and setup.py location
    app_name = f"BIGMACLAB_MANAGER_{version}"
    setup_py_path = create_setup_py(output_directory, app_name, version, script_path)

    try:
        # Change the current working directory to output_directory
        cwd = os.getcwd()
        os.chdir(output_directory)

        # Run py2app to build the .app and .dmg
        subprocess.run(['python3', 'setup.py', 'py2app'], check=True)

        # Move .dmg to output directory
        dmg_file = os.path.join(output_directory, "dist", f"{app_name}.dmg")
        if os.path.exists(dmg_file):
            shutil.move(dmg_file, os.path.join(output_directory, f"{app_name}.dmg"))
            print(f"Finished building {app_name}.dmg in {output_directory}")

    finally:
        # Clean up setup.py and build artifacts
        if os.path.exists(setup_py_path):
            os.remove(setup_py_path)
        if os.path.exists(os.path.join(output_directory, 'build')):
            shutil.rmtree(os.path.join(output_directory, 'build'))
        if os.path.exists(os.path.join(output_directory, 'dist')):
            shutil.rmtree(os.path.join(output_directory, 'dist'))
        os.chdir(cwd)

if __name__ == "__main__":
    if socket.gethostname() == "BigMacServer":
        output_directory = "/Users/BigMac/BIGMACLAB_MANAGER/dmg"
    elif socket.gethostname() == "Yojuns-MacBook-Pro.local":
        output_directory = "/Users/yojunsmacbookprp/Documents/GitHub/dmg"

    # Script file path
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'BIGMACLAB_MANAGER.py')

    while True:
        # Get the version from the user
        version = input("Enter the program version: ")

        dmg_file_path = os.path.join(output_directory, f"BIGMACLAB_MANAGER_{version}.dmg")
        if os.path.exists(dmg_file_path):
            os.remove(dmg_file_path)
            print(f"\n이전 동일 버전({version}) 삭제됨\n")

        build_dmg(output_directory, version, script_path)
        os.system("clear")

        now = datetime.now()
        current_time = now.strftime("%Y-%m-%d %H:%M")
        print(f"{current_time} BIGMACLAB_MANAGER_{version}.dmg built successfully\n")
