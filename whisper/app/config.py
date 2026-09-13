import os

from dotenv import load_dotenv

load_dotenv()

# GPU 서버 주소 — manager/server와 동일한 env 키를 쓴다 (예: http://localhost:9000/gpu)
GPU_SERVER_URL = (os.getenv("GPU_SERVER_URL") or "").rstrip("/")

# 업로드된 음성 파일 저장 위치
DATA_PATH = os.getenv(
    "WHISPER_DATA_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"),
)
os.makedirs(DATA_PATH, exist_ok=True)

# 업로드 허용 확장자(ffmpeg가 처리 가능한 오디오/영상 포맷)와 용량 상한
ALLOWED_EXTS = {
    ".mp3",
    ".wav",
    ".m4a",
    ".aac",
    ".ogg",
    ".opus",
    ".flac",
    ".wma",
    ".amr",
    ".webm",
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
}
MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024  # 2GB
