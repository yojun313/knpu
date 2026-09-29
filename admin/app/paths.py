"""관리자 대시보드 런타임 데이터 위치 (Git 목록 설정 · AI 커밋 설정 등).

저장소 밖(기본 ~/.knpu_admin)에 둔다 — admin 은 pm2 watch 로 돌기 때문에 프로젝트 안에
쓰면 설정을 저장할 때마다 서버가 재시작된다.
"""

import os
from pathlib import Path

# admin/app/paths.py → knpu 저장소 루트
KNPU_ROOT = Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    configured = os.getenv("KNPU_ADMIN_DATA_DIR")
    path = Path(configured).expanduser() if configured else Path.home() / ".knpu_admin"
    path.mkdir(parents=True, exist_ok=True)
    return path
