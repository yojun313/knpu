import os
import subprocess
import socket
import shutil

def create_spec_file(original_spec_file, new_spec_file, exe_name):
    with open(original_spec_file, 'r') as file:
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
        subprocess.run([
            'pyinstaller',
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
        output_directory = "D:/BIGMACLAB/BIGMACLAB_MANAGER"

    # Spec file path
    spec_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'BIGMACLAB_MANAGER.spec')

    # Get the version from the user
    version = input("Enter the program version: ")

    build_exe_from_spec(spec_file, output_directory, version)
