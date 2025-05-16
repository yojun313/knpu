"""
BIGMACLAB_MANAGER · persistent settings helper
----------------------------------------------

- Qt 의 `QSettings` 래퍼
- 기본값 자동 채우기
- 편의 함수: `get_setting`, `set_setting`, `update_settings`, `all_settings`
"""
from __future__ import annotations

from typing import Any, Mapping
from PyQt5.QtCore import QSettings

# ── 1) Persistent store 객체 ───────────────────────────────────────────────────
_qsettings = QSettings("BIGMACLAB", "BIGMACLAB_MANAGER")

# ── 2) 디폴트 값 정의 ─────────────────────────────────────────────────────────
_DEFAULTS: dict[str, Any] = {
    "Theme":            "default",
    "ScreenSize":       "default",
    "OldPostUid":       "default",
    "AutoUpdate":       "default",
    "MyDB":             "default",
    "GPT_Key":          "default",
    "DB_Refresh":       "default",
    "BootTerminal":     "default",
    "DBKeywordSort":    "default",
    "ProcessConsole":   "default",
    "LLM_model":        "ChatGPT",
    "LLM_model_name":   "ChatGPT 4",
}

# ── 3) 최초 실행 시 한 번만 기본값 주입 ────────────────────────────────────────
for key, val in _DEFAULTS.items():
    if _qsettings.value(key) is None:
        _qsettings.setValue(key, val)


# ── 4) 편의 함수들 ────────────────────────────────────────────────────────────
def get_setting(key: str, default: Any | None = None) -> Any:
    """단일 설정값 반환 (없으면 default)"""
    return _qsettings.value(key, default)


def set_setting(key: str, value: Any) -> None:
    """단일 설정값 저장 & 즉시 플러시"""
    _qsettings.setValue(key, value)
    _qsettings.sync()


def update_settings(**kwargs: Any) -> None:
    """여러 값을 한꺼번에 저장  
       `update_settings(Theme='dark', ScreenSize='max')`
    """
    for k, v in kwargs.items():
        _qsettings.setValue(k, v)
    _qsettings.sync()


def all_settings() -> dict[str, Any]:
    """딕셔너리 형태로 전체 설정 반환 (기본값 포함)"""
    return {k: get_setting(k, _DEFAULTS[k]) for k in _DEFAULTS}
