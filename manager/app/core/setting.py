"""
MANAGER · persistent settings helper
----------------------------------------------

- Qt 의 `QSettings` 래퍼
- 기본값 자동 채우기
- 편의 함수: `get_setting`, `set_setting`, `update_settings`, `all_settings`
"""

from __future__ import annotations

from typing import Any
from PySide6.QtCore import QSettings
from config import VERSION

_qsettings = QSettings("KNPU", "MANAGER")

_DEFAULTS: dict[str, Any] = {
    "ThemeStyle": "default",  # default | glass | neu | mesh (웹 서비스들과 같은 4종 스킨)
    "ThemeMode": "light",  # light | dark
    "ScreenSize": "default",
    "OldPostUid": "default",
    "AutoUpdate": "default",
    "MyDB": "default",
    "GPT_Key": "default",
    "DB_Refresh": "default",
    "BootTerminal": "default",
    "DBKeywordSort": "default",
    "ProcessConsole": "default",
    "LLM_model": "Server LLM",
    "LLM_model_name": "ChatGPT 4",
    "LastVersion": f"{VERSION}",
}

for key, val in _DEFAULTS.items():
    if _qsettings.value(key) is None:
        _qsettings.setValue(key, val)

# 구버전 마이그레이션: 예전엔 "Theme"(default|dark) 하나로 라이트/다크만 구분했다.
# 그 값이 남아있고 아직 옮기지 않았으면 ThemeMode로 변환하고, 스킨은 기존 디자인(default)으로 둔다.
_legacy_theme = _qsettings.value("Theme")
if _legacy_theme is not None and _qsettings.value("ThemeMigrated") is None:
    _qsettings.setValue("ThemeMode", "dark" if _legacy_theme == "dark" else "light")
    _qsettings.setValue("ThemeStyle", "default")
    _qsettings.setValue("ThemeMigrated", True)
    _qsettings.sync()


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
