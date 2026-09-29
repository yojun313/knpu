"""AI 커밋 메시지 (VS Code Copilot 처럼): 커밋할 변경(diff)을 OpenAI 호환 API 에 보내 메시지를 받는다.

- 설정(주소 · 모델 · 토큰 · 언어)은 대시보드 데이터 폴더의 ai-commit.json (권한 600) 에 둔다.
  토큰은 서버 밖(브라우저)으로 절대 내보내지 않는다 — 설정 여부만 알려 준다.
- 저장소는 읽기만 한다 (git diff · status · log). 스테이징 같은 변경은 하지 않는다.
"""

import json
import os
import re
import secrets
from pathlib import Path

import httpx

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
    data = _read()
    own = bool(data.get("base_url") and data.get("model"))
    return {
        "base_url": data.get("base_url") or "",
        "model": data.get("model") or "",
        "language": data.get("language") or "auto",
        "token_set": bool(data.get("token")),
        # 따로 설정하지 않으면 KNPU 공용 LLM(설정 창의 'AI 모델' = 사용자별 로컬/내 GPT API)을 쓴다.
        "configured": True,
        "source": "custom" if own else "knpu",
    }


def save_settings(base_url: str, model: str, token: str | None, language: str) -> dict:
    """token 이 None 이면 기존 토큰 유지, "" 이면 지운다."""
    base_url = (base_url or "").strip().rstrip("/")
    model = (model or "").strip()
    if base_url and not re.match(r"^https?://[^\s/?#]+(?:/[^\s?#]*)?$", base_url):
        raise ValueError(
            "API 주소는 http:// 또는 https:// 로 시작해야 해요 (예: https://api.openai.com/v1)."
        )
    if len(base_url) > 500:
        raise ValueError("API 주소가 너무 길어요.")
    if model and not _MODEL.match(model):
        raise ValueError("모델 이름이 올바르지 않아요.")
    if language not in LANGUAGES:
        raise ValueError("언어 설정이 올바르지 않아요.")
    data = _read()
    data.update({"base_url": base_url, "model": model, "language": language})
    if token is not None:
        token = token.strip()
        if len(token) > 1000 or any(c in token for c in "\r\n"):
            raise ValueError("토큰 형식이 올바르지 않아요.")
        data["token"] = token
    path = _settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False)
    os.replace(tmp, path)
    return public_settings()


def _validated_base_url(base_url: str) -> str:
    base_url = (base_url or "").strip().rstrip("/")
    if not re.match(r"^https?://[^\s/?#]+(?:/[^\s?#]*)?$", base_url):
        raise ValueError("API 주소는 http:// 또는 https:// 로 시작해야 해요.")
    if len(base_url) > 500:
        raise ValueError("API 주소가 너무 길어요.")
    return base_url


def discover_model(base_url: str, token: str | None = None) -> dict:
    """OpenAI 호환 /models 에서 현재 사용 가능한 모델을 읽고 자동 선택한다."""
    base_url = _validated_base_url(base_url)
    if base_url.endswith("/chat/completions"):
        models_url = base_url[: -len("/chat/completions")] + "/models"
    elif base_url.endswith("/models"):
        models_url = base_url
    else:
        models_url = base_url + "/models"

    saved = _read()
    if token is None and saved.get("base_url", "").rstrip("/") == base_url:
        token = saved.get("token") or ""
    token = (token or "").strip()
    if len(token) > 1000 or any(char in token for char in "\r\n"):
        raise ValueError("토큰 형식이 올바르지 않아요.")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        with httpx.Client(timeout=15.0, follow_redirects=False) as client:
            response = client.get(models_url, headers=headers)
    except httpx.TimeoutException as error:
        raise AICommitError("모델 목록 조회 시간이 초과됐어요.") from error
    except httpx.HTTPError as error:
        raise AICommitError(
            f"모델 목록을 가져오지 못했어요: {type(error).__name__}"
        ) from error
    if response.status_code >= 400:
        raise AICommitError(
            f"모델 목록 조회 실패 ({response.status_code}). API 주소와 토큰을 확인해 주세요."
        )
    try:
        payload = response.json()
        rows = (
            payload.get("data", payload.get("models", []))
            if isinstance(payload, dict)
            else []
        )
        models = [
            row.get("id") or row.get("name")
            for row in rows
            if isinstance(row, dict)
            and isinstance(row.get("id") or row.get("name"), str)
        ]
    except (ValueError, TypeError, AttributeError) as error:
        raise AICommitError("모델 목록 응답이 OpenAI 호환 형식이 아니에요.") from error
    models = list(dict.fromkeys(model.strip() for model in models if model.strip()))
    if not models:
        raise AICommitError("API 주소에서 사용 가능한 모델을 찾지 못했어요.")
    # 서버가 활성 모델을 표시하면 그것을 우선하고, 아니면 /models 첫 항목을 기본으로 쓴다.
    active = next(
        (
            row.get("id") or row.get("name")
            for row in rows
            if isinstance(row, dict)
            and (row.get("loaded") or row.get("active") or row.get("currently_loaded"))
            and isinstance(row.get("id") or row.get("name"), str)
        ),
        models[0],
    )
    return {"model": active, "models": models}


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
            "커밋할 변경이 없어요."
            if include_all
            else "스테이징된 변경이 없어요. 파일을 스테이징하거나 '모든 변경 포함'을 켜 주세요."
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
    """별도 AI 설정이 없을 때: KNPU 공용 LLM(사용자별 설정 · 사용량 기록)으로 만든다."""
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
        raise AICommitError(f"AI 커밋 메시지를 만들지 못했어요: {error}") from error
    return call.result.text or ""


def generate(repository_id: str, include_all: bool, uid: str | None = None) -> dict:
    settings = _read()
    use_knpu = not (settings.get("base_url") and settings.get("model"))
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
    if use_knpu:
        message = _clean(_generate_with_knpu_llm(uid, prompt))
        if not message:
            raise AICommitError("AI 가 빈 메시지를 돌려줬어요.")
        return {"message": message[:5000], "truncated": "생략" in changes["diff"][-40:]}
    headers = {"Content-Type": "application/json"}
    if settings.get("token"):
        headers["Authorization"] = f"Bearer {settings['token']}"
    body = {
        "model": settings["model"],
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT, follow_redirects=False) as client:
            response = client.post(
                _endpoint(settings["base_url"]), headers=headers, json=body
            )
    except httpx.TimeoutException as error:
        raise AICommitError("AI 응답이 너무 늦어요 (60초 초과).") from error
    except httpx.HTTPError as error:
        raise AICommitError(
            f"AI 서버에 연결하지 못했어요: {type(error).__name__}"
        ) from error
    if response.status_code >= 400:
        detail = ""
        try:
            payload = response.json()
            detail = (
                (payload.get("error") or {}).get("message")
                if isinstance(payload.get("error"), dict)
                else payload.get("error") or payload.get("detail") or ""
            )
        except ValueError:
            detail = response.text[:200]
        raise AICommitError(
            f"AI 요청 실패 ({response.status_code}){': ' + str(detail)[:300] if detail else ''}"
        )
    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise AICommitError(
            "AI 응답 형식을 알 수 없어요 (OpenAI 호환 /chat/completions 인지 확인해 주세요)."
        ) from error
    message = _clean(content if isinstance(content, str) else "")
    if not message:
        raise AICommitError("AI 가 빈 메시지를 돌려줬어요.")
    return {"message": message[:5000], "truncated": "생략" in changes["diff"][-40:]}
