"""챗봇 설정 (환경 변수로 바꿀 수 있다)."""

import os
from pathlib import Path

# system/chatbot/config.py → knpu 저장소 루트
REPO_ROOT = Path(os.getenv("CHATBOT_REPO_ROOT") or Path(__file__).resolve().parents[2])


def data_dir() -> Path:
    """색인 · 대화 백업 위치. 저장소 밖에 둔다(pm2 watch 가 재시작하지 않게)."""
    path = Path(
        os.getenv("CHATBOT_DATA_DIR") or Path.home() / ".knpu_chatbot"
    ).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def homepage_api_base() -> str:
    """홈페이지 공개 API 주소(DB에 직접 붙지 못할 때 쓰는 대체 경로)."""
    configured = os.getenv("CHATBOT_HOMEPAGE_API")
    if configured:
        return configured.rstrip("/")
    try:
        from system.endpoints import _config

        cfg = _config()
        return f"https://{cfg['services']['homepage']['prod_domain']}"
    except Exception:
        return "https://knpu.re.kr"


MAX_TURNS = int(os.getenv("CHATBOT_MAX_TURNS", "12"))
TIME_BUDGET_S = float(os.getenv("CHATBOT_TIME_BUDGET_S", "200"))
ANSWER_TOKENS = int(
    os.getenv("CHATBOT_MAX_TOKENS", "6000")
)  # 추론 모델은 생각에도 토큰을 쓴다
HOMEPAGE_CACHE_S = 600
CODE_RESCAN_S = 300
