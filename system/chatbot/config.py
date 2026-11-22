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
# 답변을 쓰는 대로 화면에 흘려보낸다(체감 속도). 스트리밍을 못 하는 서버면 자동으로 일반 호출로 바뀐다.
STREAM = os.getenv("CHATBOT_STREAM", "1").lower() not in ("0", "false", "off")
# 첫 LLM 호출 전에 질문으로 관련 자료를 미리 찾아 넣는다(LLM 왕복 1~2번 절약)
PREFETCH = os.getenv("CHATBOT_PREFETCH", "1").lower() not in ("0", "false", "off")
# 추론 모델의 생각 길이(minimal/low/medium/high, 빈 값이면 모델 기본값). 지원하는 모델에만 전달된다
REASONING_EFFORT = os.getenv("CHATBOT_REASONING_EFFORT", "low").strip().lower()
HOMEPAGE_CACHE_S = 600
CODE_RESCAN_S = 300
