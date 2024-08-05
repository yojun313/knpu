import os
import subprocess
import socket


def build_exe_from_spec(spec_file, output_directory, version):
    # Ensure the output directory exists
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    print(f"Building exe for {spec_file}...")

    # Define the output executable name with version
    exe_name = f"BIGMACLAB_MANAGER_{version}"

    # Run pyinstaller with the spec file
    subprocess.run([
        'pyinstaller',
        '--distpath', output_directory,
        '--workpath', os.path.join(output_directory, 'build'),
        spec_file
    ])

    print(f"Finished building {exe_name}.exe")


if __name__ == "__main__":
    # Directory where the exe files will be output
    if socket.gethostname() == "Yojuns-MacBook-Pro.local":
        output_directory = '/Users/yojunsmacbookprp/Documents/BIGMACLAB/CRAWLER'

    elif socket.gethostname() == "BigMacServer":
        output_directory = "D:/BIGMACLAB/CRAWLER"

    # Spec file path
    spec_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'BIGMACLAB_MANAGER.spec')

    # Get the version from the user
    version = input("Enter the program version: ")

    build_exe_from_spec(spec_file, output_directory, version)
