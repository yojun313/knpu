import os
from dotenv import load_dotenv

load_dotenv()

# Path
EXE_DIRECTORY = "D:/knpu/MANAGER/exe"
OUTPUT_DIRECTORY = "D:/knpu/MANAGER/output"
VENV_PYTHON = r"C:/GitHub/knpu/venv/Scripts/python.exe"
INNO_SETUP_EXE = r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"


# Cloudflare R2
ACCESS_KEY_ID = os.getenv("ACCESS_KEY_ID")
SECRET_ACCESS_KEY = os.getenv("SECRET_ACCESS_KEY")
ACCOUNT_ID = os.getenv("ACCOUNT_ID")
BUCKET_NAME = os.getenv("BUCKET_NAME")
R2_ENDPOINT = f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com"
