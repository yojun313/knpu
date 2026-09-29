"""전역 LLM 설정 — .env 하나로 프로젝트 전체가 같은 LLM을 쓴다.

OpenAI 호환 엔드포인트면 무엇이든 붙는다(vLLM, Ollama, LM Studio, LiteLLM,
OpenAI 공식 API, manager 서버의 /llm 프록시 등).

    LLM_BASE_URL   : OpenAI 호환 base URL (…/v1 까지)
    LLM_API_KEY    : API 키 (없으면 OPENAI_API_KEY를 재사용)
    모델 이름은 매 요청 전에 /models 에서 자동 조회한다(LLM_MODEL은 사용하지 않음).
    LLM_TIMEOUT    : 요청 타임아웃(초)
    LLM_MAX_RETRIES: 엔드포인트별 재시도 횟수(기본 1)

주 엔드포인트가 죽었을 때 쓸 폴백(기존 코드가 모두 이 구조였다):

    LLM_FALLBACK_BASE_URL / LLM_FALLBACK_API_KEY / LLM_FALLBACK_MODEL
"""

import os

from dotenv import load_dotenv

load_dotenv()

# 로컬 vLLM 기본 포트. 기존 complaint/manager 코드가 쓰던 값과 같다.
_DEFAULT_BASE_URL = "http://localhost:9001/v1"
_DEFAULT_FALLBACK_MODEL = "gpt-5-mini"
_OPENAI_BASE_URL = "https://api.openai.com/v1"


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def _normalize_base_url(url: str | None) -> str | None:
    """끝의 슬래시만 정리한다. /v1 을 자동으로 붙이지는 않는다 —
    manager 프록시처럼 /llm/v1/openai 로 끝나는 경우도 있어서다."""
    url = _clean(url)
    return url.rstrip("/") if url else None


class LLMSettings:
    def __init__(self, env: dict | None = None):
        env = env if env is not None else os.environ

        def get(key: str) -> str | None:
            return _clean(env.get(key))

        self.base_url = _normalize_base_url(get("LLM_BASE_URL")) or _DEFAULT_BASE_URL
        # 키를 따로 주지 않았으면 기존 OPENAI_API_KEY를 그대로 쓴다.
        self.api_key = get("LLM_API_KEY") or get("OPENAI_API_KEY")
        # 주 엔드포인트는 현재 제공 중인 모델을 매 요청마다 조회한다.
        self.model = None  # 기존 설정 조회 코드와의 호환성을 유지한다.

        try:
            self.timeout = float(get("LLM_TIMEOUT") or 120)
        except ValueError:
            self.timeout = 120.0

        # SDK 기본값(2)은 죽은 엔드포인트에서 폴백까지 가는 시간을 3배로 늘린다.
        # 일시적 429/5xx는 한 번만 재시도하고 바로 폴백으로 넘긴다.
        try:
            self.max_retries = int(get("LLM_MAX_RETRIES") or 1)
        except ValueError:
            self.max_retries = 1

        self.system_prompt = get("LLM_SYSTEM_PROMPT") or "You are a helpful assistant."

        # ---- 폴백 ----
        fallback_key = get("LLM_FALLBACK_API_KEY") or get("OPENAI_API_KEY")
        fallback_url = _normalize_base_url(get("LLM_FALLBACK_BASE_URL"))
        # 폴백 키만 있으면 OpenAI 공식 API를 쓴다는 뜻으로 본다.
        if fallback_key and not fallback_url:
            fallback_url = _OPENAI_BASE_URL

        self.fallback_base_url = fallback_url
        self.fallback_api_key = fallback_key
        self.fallback_model = get("LLM_FALLBACK_MODEL") or (
            _DEFAULT_FALLBACK_MODEL if fallback_url else None
        )

    @property
    def has_fallback(self) -> bool:
        return bool(self.fallback_base_url and self.fallback_api_key)

    def __repr__(self) -> str:  # 키는 절대 노출하지 않는다
        return (
            f"LLMSettings(base_url={self.base_url!r}, model={self.model or 'auto'!r}, "
            f"api_key={'set' if self.api_key else 'unset'}, "
            f"fallback={'set' if self.has_fallback else 'none'})"
        )


_settings: LLMSettings | None = None


def get_settings() -> LLMSettings:
    global _settings
    if _settings is None:
        _settings = LLMSettings()
    return _settings


def reload_settings() -> LLMSettings:
    """설정을 다시 읽는다.

    override=False를 쓰는 것이 중요하다. 실제 환경변수(systemd/docker/CI에서
    주입한 값)가 .env보다 우선해야 한다. override=True로 두면 프로세스 환경을
    .env가 덮어써서, 배포 환경에서 주입한 설정이 조용히 무시된다.

    설정 로직만 시험하려면 LLMSettings(env={...})로 직접 주입하는 편이 낫다.
    """
    global _settings
    load_dotenv()
    _settings = LLMSettings()
    return _settings
