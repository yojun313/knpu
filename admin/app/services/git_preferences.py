import json
import os
import re
import tempfile
import threading
from pathlib import Path
from typing import Any

from app.paths import data_dir
from pydantic import BaseModel, Field, field_validator

REPOSITORY_ID = re.compile(r"^[0-9a-f]{16}$")
FOLDER_ID = re.compile(r"^[A-Za-z0-9_-]{1,32}$")


def _unique_ids(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for value in values:
        if REPOSITORY_ID.match(value) and value not in seen:
            seen.add(value)
            result.append(value)
    return result


class GitFolder(BaseModel):
    id: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=60)
    collapsed: bool = False
    repositories: list[str] = Field(default_factory=list, max_length=500)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not FOLDER_ID.match(value):
            raise ValueError("잘못된 폴더 ID")
        return value

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("폴더 이름이 비었습니다.")
        return value

    @field_validator("repositories")
    @classmethod
    def validate_repositories(cls, value: list[str]) -> list[str]:
        return _unique_ids(value)


class GitPreferences(BaseModel):
    """저장소 목록 표시 설정. 저장소 ID 는 경로 해시(16자리 hex)다."""

    folders: list[GitFolder] = Field(default_factory=list, max_length=100)
    order: list[str] = Field(default_factory=list, max_length=500)
    hidden: list[str] = Field(default_factory=list, max_length=500)
    favorites: list[str] = Field(default_factory=list, max_length=500)
    aliases: dict[str, str] = Field(default_factory=dict)
    # 목록 정렬: 변경사항 우선 / 최근 커밋 / 이름 / 직접 지정(끌어서 정한 순서)
    sort: str = "changes"

    @field_validator("sort")
    @classmethod
    def validate_sort(cls, value: str) -> str:
        return value if value in {"changes", "recent", "name", "manual"} else "changes"

    @field_validator("order", "hidden", "favorites")
    @classmethod
    def validate_ids(cls, value: list[str]) -> list[str]:
        return _unique_ids(value)

    @field_validator("aliases")
    @classmethod
    def validate_aliases(cls, value: dict[str, str]) -> dict[str, str]:
        cleaned = {}
        for key, alias in list(value.items())[:500]:
            alias = str(alias).strip()[:60]
            if REPOSITORY_ID.match(key) and alias:
                cleaned[key] = alias
        return cleaned

    def normalized(self) -> "GitPreferences":
        """한 저장소가 여러 폴더에 들어가지 않게 하고, 폴더 ID 중복을 없앤다."""
        placed: set[str] = set()
        folders = []
        folder_ids: set[str] = set()
        for folder in self.folders:
            if folder.id in folder_ids:
                continue
            folder_ids.add(folder.id)
            repositories = [repo for repo in folder.repositories if repo not in placed]
            placed.update(repositories)
            folders.append(folder.model_copy(update={"repositories": repositories}))
        order = [repo for repo in self.order if repo not in placed]
        return self.model_copy(update={"folders": folders, "order": order})


class GitPreferencesStore:
    _lock = threading.Lock()

    @staticmethod
    def _path() -> Path:
        return data_dir() / "git_preferences.json"

    @classmethod
    def load(cls) -> GitPreferences:
        path = cls._path()
        with cls._lock:
            try:
                raw: Any = json.loads(path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                return GitPreferences()
            except (OSError, ValueError):
                return GitPreferences()
        try:
            return GitPreferences.model_validate(raw).normalized()
        except ValueError:
            return GitPreferences()

    @classmethod
    def save(cls, preferences: GitPreferences) -> GitPreferences:
        preferences = preferences.normalized()
        path = cls._path()
        payload = json.dumps(preferences.model_dump(), ensure_ascii=False, indent=2)
        with cls._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            # 원자적 교체: 쓰는 도중 서버가 죽어도 기존 설정이 깨지지 않는다.
            fd, temp_name = tempfile.mkstemp(
                dir=path.parent, prefix=".git_preferences."
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(payload)
                os.chmod(temp_name, 0o600)
                os.replace(temp_name, path)
            except BaseException:
                Path(temp_name).unlink(missing_ok=True)
                raise
        return preferences
