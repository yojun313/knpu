"""AI 커밋 메시지 (VS Code Copilot 처럼): 커밋할 변경(diff)을 OpenAI 호환 API 에 보내 메시지를 받는다.

- 설정(주소 · 모델 · 토큰 · 언어)은 대시보드 데이터 폴더의 ai-commit.json (권한 600) 에 둔다.
  토큰은 서버 밖(브라우저)으로 절대 내보내지 않는다 — 설정 여부만 알려 준다.
- 저장소는 읽기만 한다 (git diff · status · log). 스테이징 같은 변경은 하지 않는다.
"""

from system.llm_activity import tracked

import json
import os
import re
import secrets
from pathlib import Path


from app.paths import data_dir
from app.services.repo_git_service import GitService

MAX_DIFF_CHARS = 24000
MAX_UNTRACKED_FILES = 20
MAX_UNTRACKED_LINES = 40
REQUEST_TIMEOUT = 60.0
LANGUAGES = {"auto", "ko", "en"}
_MODEL = re.compile(r"^[\w.:/\-\[\]@+]{1,120}$")


class AICommitError(RuntimeError):
    pass


# ── 설정 ──────────────────────────────────────────────────────────────────────


def _settings_file() -> Path:
    return data_dir() / "ai-commit.json"


def _read() -> dict:
    try:
        data = json.loads(_settings_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def public_settings() -> dict:
    """커밋 메시지는 항상 연구실 전역 AI 모델로 만든다. 고를 수 있는 것은 메시지 언어뿐이다."""
    data = _read()
    return {
        "language": data.get("language") or "auto",
        "configured": True,
        "source": "knpu",
    }


def save_settings(language: str) -> dict:
    if language not in LANGUAGES:
        raise ValueError("언어 설정이 올바르지 않습니다.")
    data = _read()
    data["language"] = language
    path = _settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False)
    os.replace(tmp, path)
    return public_settings()


# ── 변경 모으기 (읽기만) ─────────────────────────────────────────────────────────


def _git(path: Path, *args: str) -> str:
    return GitService._run(path, *args).stdout or ""


def collect_changes(repository_id: str, include_all: bool) -> dict:
    repository = GitService._get_repository(repository_id)
    path = repository.path
    has_head = GitService._has_head(path)
    if include_all:
        diff = (
            _git(path, "diff", "--no-ext-diff", "HEAD")
            if has_head
            else _git(path, "diff", "--no-ext-diff", "--cached")
            + _git(path, "diff", "--no-ext-diff")
        )
        untracked = [
            line
            for line in _git(
                path, "ls-files", "--others", "--exclude-standard", "-z"
            ).split("\0")
            if line
        ]
    else:
        diff = _git(path, "diff", "--no-ext-diff", "--cached")
        untracked = []
    # 새 파일(추적 안 됨)은 앞부분만
    for name in untracked[:MAX_UNTRACKED_FILES]:
        file = (path / name).resolve()
        try:
            file.relative_to(path.resolve())
            if not file.is_file() or file.stat().st_size > 512 * 1024:
                diff += f"\nnew file: {name}\n"
                continue
            lines = file.read_text(encoding="utf-8", errors="replace").splitlines()[
                :MAX_UNTRACKED_LINES
            ]
        except (OSError, ValueError):
            continue
        diff += f"\nnew file: {name}\n" + "\n".join(f"+{line}" for line in lines) + "\n"
    if len(untracked) > MAX_UNTRACKED_FILES:
        diff += f"\n(새 파일 {len(untracked) - MAX_UNTRACKED_FILES}개 더)\n"
    if not diff.strip():
        raise AICommitError(
            "커밋할 변경이 없습니다."
            if include_all
            else "스테이징된 변경이 없습니다. 파일을 스테이징하거나 '모든 변경 포함'을 켜 주시기 바랍니다."
        )
    truncated = len(diff) > MAX_DIFF_CHARS
    stat_args = (
        ["diff", "--stat", "HEAD"]
        if include_all and has_head
        else ["diff", "--stat", "--cached"]
    )
    stat = _git(path, *stat_args).strip()
    recent = _git(path, "log", "-8", "--pretty=format:%s").strip() if has_head else ""
    return {
        "diff": diff[:MAX_DIFF_CHARS]
        + ("\n… (diff 가 길어 뒷부분은 생략)" if truncated else ""),
        "stat": stat[-3000:],
        "recent": recent,
        "branch": _git(path, "rev-parse", "--abbrev-ref", "HEAD").strip()
        if has_head
        else "",
    }


# ── 생성 ──────────────────────────────────────────────────────────────────────

_SYSTEM = (
    "You write git commit messages for the given changes. Reply with the commit message only — no code fences, "
    "no quotes, no explanations. Format: a concise summary line (imperative mood, at most 72 characters), then, "
    "only if it helps, a blank line and a short body of '- ' bullet points explaining what changed and why. "
    "Do not invent changes that are not in the diff."
)
_LANGUAGE_HINT = {
    "auto": "Write in the same language and style as the recent commit subjects if there are any; otherwise English.",
    "ko": "Write the message in Korean.",
    "en": "Write the message in English.",
}


def _endpoint(base_url: str) -> str:
    return (
        base_url
        if base_url.endswith("/chat/completions")
        else f"{base_url}/chat/completions"
    )


def _clean(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[\w-]*\n?|\n?```$", "", text).strip()
    text = re.sub(
        r"<think>.*?</think>", "", text, flags=re.DOTALL
    ).strip()  # 생각 과정을 내보내는 모델 대비
    return text.strip('"').strip()


def _generate_with_knpu_llm(uid: str | None, prompt: str) -> str:
    """연구실 전역 AI 모델(설정 > 전역 AI 모델의 우선순위)로 만든다."""
    from system.llm import LLMError, user_llm

    try:
        call = user_llm.chat_for_user(
            uid,
            [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": prompt},
            ],
            purpose="Admin Git AI commit message",
            max_tokens=4000,
            temperature=0.2,
        )
    except LLMError as error:
        raise AICommitError(f"AI 커밋 메시지를 만들지 못했습니다: {error}") from error
    return call.result.text or ""


@tracked("AI 커밋 메시지 작성", service="admin")
def generate(repository_id: str, include_all: bool, uid: str | None = None) -> dict:
    settings = _read()
    changes = collect_changes(repository_id, include_all)
    prompt = "\n\n".join(
        part
        for part in [
            _LANGUAGE_HINT[settings.get("language") or "auto"],
            f"Branch: {changes['branch']}" if changes["branch"] else "",
            f"Recent commit subjects (style reference):\n{changes['recent']}"
            if changes["recent"]
            else "",
            f"Changed files:\n{changes['stat']}" if changes["stat"] else "",
            f"Diff:\n{changes['diff']}",
        ]
        if part
    )
    message = _clean(_generate_with_knpu_llm(uid, prompt))
    if not message:
        raise AICommitError("AI 가 빈 메시지를 반환했습니다.")
    return {"message": message[:5000], "truncated": "생략" in changes["diff"][-40:]}
