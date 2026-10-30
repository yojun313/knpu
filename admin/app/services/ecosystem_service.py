"""PM2 ecosystem.config.js 읽기 · 앱 추가 · 수정 · 삭제.

- 읽기: pm2 와 같은 방식으로 node 가 파일을 require 해서 JSON 으로 돌려준다.
- 추가: 파일 전체를 다시 쓰지 않고 `apps: [ ... ]` 의 닫는 `]` 바로 앞에 새 항목만 끼워 넣어
  기존 서식 · 주석 · 함수 값을 그대로 둔다. 쓰기 전에 node 로 다시 읽어 검증하고,
  원본은 백업한 뒤 원자적으로 교체한다.
- 수정: 해당 항목 안에서 바뀐 속성의 값만 갈아 끼운다 (폼에 없는 속성 · 주석은 그대로).
- 삭제: 해당 항목만 잘라 낸다.
- 수정 · 삭제 모두 node 로 다시 읽어, 바꾸려던 곳 말고는 모든 앱 설정이 그대로인지 확인한 뒤에만 저장한다.
- 모든 문자열 값은 json.dumps 로 이스케이프해 JS 문자열 리터럴로 넣는다 (코드 주입 방지).
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

APP_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
ENV_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
SCRIPT_CANDIDATES = [
    "run.py",
    "main.py",
    "app.py",
    "manage.py",
    "server.py",
    "server.js",
    "index.js",
    "app.js",
    "main.js",
]
_lock = threading.Lock()


class EcosystemError(Exception):
    pass


def ecosystem_path() -> Path:
    """기본: knpu 저장소의 ecosystem.prod.config.js (개발 모드면 ecosystem.dev.config.js)."""
    configured = os.getenv("PM2_ECOSYSTEM_FILE")
    if configured:
        return Path(configured).expanduser()
    from app.paths import KNPU_ROOT
    from system.endpoints import IS_DEV

    return KNPU_ROOT / (
        "ecosystem.dev.config.js" if IS_DEV else "ecosystem.prod.config.js"
    )


# pm2 · node 자식 프로세스에 물려줄 환경 변수(이 목록만 넘긴다).
_KEEP_ENV = {
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "SHELL",
    "LANG",
    "LANGUAGE",
    "TZ",
    "TERM",
    "PM2_HOME",
    "XDG_RUNTIME_DIR",
    "NVM_DIR",
    "NVM_BIN",
}


def child_env() -> dict[str, str]:
    """node / pm2 를 띄울 때 쓸 깨끗한 환경 변수.

    이 대시보드의 환경을 통째로 넘기면 안 된다.
    * pm2 의 IPC 채널 변수(NODE_CHANNEL_FD 등)를 받은 자식 node 는 없는 파일 디스크립터를 열려다 abort(-6) 로 죽는다.
    * pm2 는 start / restart --update-env 때 CLI 의 환경을 앱 환경에 덮어쓴다. 대시보드의 PORT=8009 ·
      MODE · .env 값이 다른 앱에 저장되어, 그 앱들이 모두 같은 포트를 잡으려다 죽는다
      ('전체 재시작'하면 일부 프로세스가 죽던 원인).
    그래서 실행에 꼭 필요한 기본 변수만 넘긴다.
    """
    return {
        k: v for k, v in os.environ.items() if k in _KEEP_ENV or k.startswith("LC_")
    }


def _node() -> str:
    node = shutil.which("node")
    if not node:
        raise EcosystemError("node 를 찾을 수 없습니다.")
    return node


_LOAD_JS = """
const path = process.argv[1];
const config = require(path);
const apps = Array.isArray(config) ? config : (config && config.apps) || [];
process.stdout.write(JSON.stringify(apps.map((app) => {
  const out = {};
  for (const [key, value] of Object.entries(app || {})) {
    if (['name', 'cwd', 'script', 'interpreter', 'args', 'watch', 'time', 'instances', 'exec_mode', 'autorestart'].includes(key)) out[key] = value;
  }
  return out;
})));
"""


def load_apps(path: Path | None = None) -> list[dict]:
    path = path or ecosystem_path()
    if not path.is_file():
        return []
    try:
        result = subprocess.run(
            [_node(), "-e", _LOAD_JS, str(path.resolve())],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            env=child_env(),
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise EcosystemError("ecosystem 파일을 읽지 못했습니다.") from error
    if result.returncode != 0:
        detail = (
            result.stderr.strip().splitlines()[-1]
            if result.stderr.strip()
            else f"node 종료 코드 {result.returncode}"
        )
        raise EcosystemError(f"ecosystem 파일을 해석하지 못했습니다: {detail}")
    try:
        apps = json.loads(result.stdout or "[]")
    except ValueError as error:
        raise EcosystemError("ecosystem 파일 형식이 올바르지 않습니다.") from error
    return [app for app in apps if isinstance(app, dict)]


_LOAD_FULL_JS = """
const path = process.argv[1];
const config = require(path);
const apps = Array.isArray(config) ? config : (config && config.apps) || [];
process.stdout.write(JSON.stringify(apps));
"""


def _load_full(path: Path) -> list:
    """앱 설정 전체 (검증용 비교에 쓴다. 함수 값은 JSON 에서 빠진다)."""
    try:
        result = subprocess.run(
            [_node(), "-e", _LOAD_FULL_JS, str(path.resolve())],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            env=child_env(),
        )
        if result.returncode != 0:
            raise EcosystemError("ecosystem 파일을 해석하지 못했습니다.")
        apps = json.loads(result.stdout or "[]")
    except (OSError, subprocess.TimeoutExpired, ValueError) as error:
        raise EcosystemError("ecosystem 파일을 읽지 못했습니다.") from error
    if not isinstance(apps, list):
        raise EcosystemError("ecosystem 파일 형식이 올바르지 않습니다.")
    return apps


def inspect_directory(cwd: str) -> dict:
    """작업 폴더를 보고 실행 파일 · 인터프리터를 추천한다."""
    directory = Path(os.path.expanduser(cwd or "")).resolve() if cwd else None
    if directory is None or not directory.is_dir():
        return {"exists": False}
    script = next(
        (name for name in SCRIPT_CANDIDATES if (directory / name).is_file()), ""
    )
    interpreter = ""
    if script.endswith(".py"):
        # knpu 처럼 가상환경이 저장소 루트에 있는 경우도 찾는다(최대 3단계 위까지)
        interpreter = "python3"
        for folder in [directory, *list(directory.parents)[:3]]:
            venv = folder / ".venv" / "bin" / "python"
            if venv.exists():
                interpreter = str(venv)
                break
    return {
        "exists": True,
        "cwd": str(directory),
        "name": re.sub(r"[^A-Za-z0-9._-]+", "-", directory.name)
        .strip("-._")
        .lower()[:64],
        "script": script,
        "interpreter": interpreter,
    }


def _mask_code(source: str, string_fill: str = " ") -> str:
    """문자열 · 템플릿 문자열 · 주석을 같은 길이의 공백으로 가린다 (위치는 그대로).

    string_fill 을 주면 문자열은 그 글자로 채운다 (값이 문자열뿐인 속성도 공백으로 사라지지 않게)."""
    out = list(source)
    index, length = 0, len(source)
    while index < length:
        char = source[index]
        fill = " "
        if char in "\"'`":
            fill = string_fill
            start = index
            index += 1
            while index < length and source[index] != char:
                index += 2 if source[index] == "\\" else 1
            stop = min(index + 1, length)
        elif source.startswith("//", index):
            start = index
            newline = source.find("\n", index)
            stop = length if newline < 0 else newline
        elif source.startswith("/*", index):
            start = index
            close = source.find("*/", index + 2)
            stop = length if close < 0 else close + 2
        else:
            index += 1
            continue
        for position in range(start, stop):
            if out[position] != "\n":
                out[position] = fill
        index = stop
    return "".join(out)


def _find_apps_array_end(source: str) -> int:
    """코드 부분의 `apps: [` 와 짝이 맞는 `]` 위치."""
    masked = _mask_code(source)
    match = re.search(r"\bapps\s*:\s*\[", masked)
    if not match:
        raise EcosystemError("ecosystem 파일에서 apps 배열을 찾지 못했습니다.")
    depth = 0
    for index in range(match.end() - 1, len(masked)):
        char = masked[index]
        if char in "[{(":
            depth += 1
        elif char in "]})":
            depth -= 1
            if depth == 0:
                return index
    raise EcosystemError("apps 배열의 끝을 찾지 못했습니다.")


def _entry_source(app: dict, indent: str, step: str) -> str:
    lines = [f"{indent}{{"]
    fields = list(app.items())
    for position, (key, value) in enumerate(fields):
        comma = "," if position < len(fields) - 1 else ""
        if key == "env":
            lines.append(f"{indent}{step}env: {{")
            env_items = list(value.items())
            for env_position, (env_key, env_value) in enumerate(env_items):
                env_comma = "," if env_position < len(env_items) - 1 else ""
                lines.append(
                    f"{indent}{step}{step}{env_key}: {json.dumps(env_value, ensure_ascii=False)}{env_comma}"
                )
            lines.append(f"{indent}{step}}}{comma}")
        else:
            lines.append(
                f"{indent}{step}{key}: {json.dumps(value, ensure_ascii=False)}{comma}"
            )
    lines.append(f"{indent}}}")
    return "\n".join(lines)


def build_app(data: dict) -> dict:
    name = str(data.get("name") or "").strip()
    if not APP_NAME.match(name):
        raise ValueError("앱 이름은 영문 · 숫자 · . _ - 로 64자 이하여야 합니다.")
    cwd = Path(os.path.expanduser(str(data.get("cwd") or "").strip())).resolve()
    if not cwd.is_dir():
        raise ValueError("작업 폴더(cwd)가 존재하지 않습니다.")
    script = str(data.get("script") or "").strip()
    if not script or "\n" in script or len(script) > 500:
        raise ValueError("실행 파일(script)을 입력해 주시기 바랍니다.")
    script_path = Path(script) if Path(script).is_absolute() else cwd / script
    if not script_path.exists() and not shutil.which(script):
        raise ValueError(f"실행 파일을 찾을 수 없습니다: {script}")
    app: dict = {"name": name, "cwd": str(cwd), "script": script}
    interpreter = str(data.get("interpreter") or "").strip()
    if interpreter:
        if "\n" in interpreter or len(interpreter) > 500:
            raise ValueError("인터프리터 값이 올바르지 않습니다.")
        if "/" in interpreter and not Path(os.path.expanduser(interpreter)).exists():
            raise ValueError(f"인터프리터를 찾을 수 없습니다: {interpreter}")
        app["interpreter"] = (
            os.path.expanduser(interpreter) if "/" in interpreter else interpreter
        )
    args = str(data.get("args") or "").strip()
    if args:
        if "\n" in args or len(args) > 500:
            raise ValueError("실행 인자(args)가 올바르지 않습니다.")
        app["args"] = args
    app["watch"] = bool(data.get("watch"))
    app["time"] = bool(data.get("time", True))
    env = {}
    for line in str(data.get("env") or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        key = key.strip()
        if not sep or not ENV_KEY.match(key):
            raise ValueError(f"환경 변수는 KEY=VALUE 형식이어야 합니다: {line[:40]}")
        if len(value) > 2000:
            raise ValueError(f"{key} 값이 너무 깁니다.")
        env[key] = value.strip()
    if env:
        app["env"] = env
    return app


def add_app(data: dict, path: Path | None = None) -> dict:
    path = path or ecosystem_path()
    app = build_app(data)
    with _lock:
        existing = load_apps(path) if path.exists() else []
        if any(item.get("name") == app["name"] for item in existing):
            raise ValueError(f"'{app['name']}' 앱이 이미 ecosystem 파일에 있습니다.")

        if path.exists():
            source = path.read_text(encoding="utf-8")
            end = _find_apps_array_end(source)
            head = source[:end].rstrip()
            # 기존 항목의 들여쓰기를 따라간다
            indent_match = re.search(r"\n([ \t]+)\{\s*\n([ \t]+)name\s*:", source)
            indent, step = ("    ", "  ")
            if indent_match:
                indent = indent_match.group(1)
                step = indent_match.group(2)[len(indent) :] or "  "
            # 주석을 가린 코드 기준으로 마지막 문자가 [ 나 , 가 아니면 쉼표를 붙인다.
            last_code = _mask_code(source[:end]).rstrip()[-1:]
            if last_code not in {"[", ","}:
                # 쉼표는 코드 끝(뒤따르는 주석 앞)에 붙여야 한다
                code_end = len(_mask_code(source[:end]).rstrip())
                head = source[:code_end] + "," + source[code_end:end].rstrip()
            separator = ""
            closing_indent = re.search(r"([ \t]*)$", source[:end]).group(1)
            new_source = f"{head}{separator}\n{_entry_source(app, indent, step)}\n{closing_indent}{source[end:]}"
        else:
            new_source = (
                "module.exports = {\n  apps: [\n"
                + _entry_source(app, "    ", "  ")
                + "\n  ]\n};\n"
            )

        expected = [a.get("name") for a in existing] + [app["name"]]
        # 쓰기 전에 node 로 다시 읽어 기존 앱 + 새 앱이 그대로 나오는지 확인한다.
        backup = _save(
            path,
            new_source,
            lambda temp: [a.get("name") for a in load_apps(temp)] == expected,
        )
    return {"app": app, "backup": backup, "path": str(path)}


def _save(path: Path, new_source: str, verify) -> str | None:
    """임시 파일에 쓰고 verify(temp) 가 참일 때만 원본을 백업하고 원자적으로 바꾼다. 백업 경로를 돌려준다."""
    fd, temp_name = tempfile.mkstemp(
        dir=path.parent, prefix=".ecosystem.", suffix=".js"
    )
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(new_source)
        if path.exists():
            os.chmod(temp, path.stat().st_mode & 0o777)
        if not verify(temp):
            raise EcosystemError(
                "수정한 ecosystem 파일을 검증하지 못해 저장하지 않았습니다."
            )
        backup = None
        if path.exists():
            stamp = time.strftime("%Y%m%d-%H%M%S")
            backup = path.with_name(f"{path.name}.bak-{stamp}")
            serial = 1
            while backup.exists():  # 같은 초에 여러 번 고쳐도 앞 백업을 덮지 않는다
                serial += 1
                backup = path.with_name(f"{path.name}.bak-{stamp}-{serial}")
            shutil.copy2(path, backup)
        os.replace(temp, path)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise
    return str(backup) if backup else None


# ── 수정 · 삭제: apps 배열의 항목 · 속성 위치 찾기 ──────────────────────────


def _skip_space(masked: str, index: int, step: int = 1) -> int:
    """가린 코드에서 공백(주석 포함)을 건너뛴다."""
    while 0 <= index < len(masked) and masked[index].isspace():
        index += step
    return index


def _split_top(masked: str, start: int, stop: int) -> list[tuple[int, int, int | None]]:
    """start..stop 사이를 깊이 0 의 쉼표로 나눈다. (시작, 끝, 뒤 쉼표 위치) 목록. 빈 조각은 뺀다."""
    parts = []
    depth = 0
    piece = start
    for index in range(start, stop):
        char = masked[index]
        if char in "[{(":
            depth += 1
        elif char in "]})":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append((piece, index, index))
            piece = index + 1
    parts.append((piece, stop, None))
    out = []
    for begin, end, comma in parts:
        begin = _skip_space(masked, begin)
        end = _skip_space(masked, end - 1, -1) + 1
        if begin < end:
            out.append((begin, end, comma))
    return out


def _app_elements(
    source: str, masked: str, count: int
) -> list[tuple[int, int, int | None]]:
    """apps 배열의 항목 위치. 모두 `{ ... }` 객체 리터럴이고 node 가 읽은 앱 수와 같아야 한다."""
    end = _find_apps_array_end(source)
    start = re.search(r"\bapps\s*:\s*\[", masked).end()
    elements = _split_top(masked, start, end)
    if len(elements) != count or any(
        masked[begin] != "{" or masked[stop - 1] != "}" for begin, stop, _ in elements
    ):
        raise EcosystemError(
            "apps 배열이 단순한 객체 목록이 아니라 자동으로 고칠 수 없습니다. 파일을 직접 수정해 주시기 바랍니다."
        )
    return elements


_KEY = re.compile(r"([A-Za-z_$][\w$]*|\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*')\s*:")


def _props(source: str, masked: str, begin: int, stop: int) -> dict[str, dict]:
    """객체 리터럴의 최상위 속성: 키 → {start, value_start, value_end, comma}."""
    props: dict[str, dict] = {}
    for start, end, comma in _split_top(masked, begin + 1, stop - 1):
        match = _KEY.match(source, start)
        if not match or match.end() > end:
            raise EcosystemError(
                "이 항목에 자동으로 고칠 수 없는 문법(전개 · 메서드 등)이 있습니다. 파일을 직접 수정해 주시기 바랍니다."
            )
        key = match.group(1)
        if key[0] in "\"'":
            key = key[1:-1]
        if key in props:
            raise EcosystemError(
                f"'{key}' 속성이 두 번 나옵니다. 파일을 직접 수정해 주시기 바랍니다."
            )
        props[key] = {
            "start": start,
            "value_start": _skip_space(masked, match.end()),
            "value_end": end,
            "comma": comma,
        }
    return props


def _cut_lines(source: str, start: int, end: int) -> tuple[int, int]:
    """잘라 낸 뒤 줄이 비게 되면 그 줄 전체(들여쓰기 · 줄바꿈 포함)를 함께 자른다."""
    line_start = source.rfind("\n", 0, start) + 1
    line_end = source.find("\n", end)
    line_end = len(source) if line_end < 0 else line_end
    if not source[line_start:start].strip() and not source[end:line_end].strip():
        return line_start, min(line_end + 1, len(source))
    return start, end


def _removal(source: str, item: tuple[int, int, int | None]) -> tuple[int, int, str]:
    """항목(또는 속성)을 뒤 쉼표까지 잘라 낸다. 마지막 항목이면 앞 항목의 쉼표가 끝 쉼표로 남는데, JS 에서 문제없다."""
    begin, end, comma = item
    return (*_cut_lines(source, begin, end if comma is None else comma + 1), "")


def _apply(source: str, edits: list[tuple[int, int, str]]) -> str:
    # 뒤에서부터 적용한다. 같은 위치면 자르기를 먼저 해서 끼워 넣은 글이 잘리지 않게 한다.
    for start, end, text in sorted(edits, key=lambda edit: edit[:2], reverse=True):
        source = source[:start] + text + source[end:]
    return source


def _indent_of(source: str, position: int) -> str | None:
    line_start = source.rfind("\n", 0, position) + 1
    head = source[line_start:position]
    return head if not head.strip() else None


def _literal(value, indent: str, step: str, multiline: bool) -> str:
    if isinstance(value, dict):
        if not value:
            return "{}"
        items = [
            f"{key}: {json.dumps(item, ensure_ascii=False)}"
            for key, item in value.items()
        ]
        if not multiline:
            return "{ " + ", ".join(items) + " }"
        inner = ",\n".join(f"{indent}{step}{item}" for item in items)
        return "{\n" + inner + f"\n{indent}}}"
    return json.dumps(value, ensure_ascii=False)


def _find(apps: list, name: str) -> int:
    index = next(
        (
            i
            for i, app in enumerate(apps)
            if isinstance(app, dict) and app.get("name") == name
        ),
        None,
    )
    if index is None:
        raise KeyError("ecosystem 파일에 없는 앱입니다.")
    return index


def _args_text(value) -> str:
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    return "" if value is None else str(value)


def get_app(name: str, path: Path | None = None) -> dict:
    """수정 폼에 채울 값. 폼에 없는 속성 이름도 알려 준다 (그대로 둔다는 안내용)."""
    path = path or ecosystem_path()
    apps = _load_full(path)
    app = apps[_find(apps, name)]
    env = app.get("env") if isinstance(app.get("env"), dict) else {}
    return {
        "name": app.get("name"),
        "cwd": app.get("cwd") or "",
        "script": app.get("script") or "",
        "interpreter": app.get("interpreter") or "",
        "args": _args_text(app.get("args")),
        "watch": bool(app.get("watch")),
        "watch_custom": isinstance(app.get("watch"), list),
        "time": bool(app.get("time")),
        "env": "\n".join(f"{key}={_env_text(value)}" for key, value in env.items()),
        "env_editable": "env" not in app or isinstance(app.get("env"), dict),
        "kept": sorted(set(app) - EDITABLE),
    }


EDITABLE = {"name", "cwd", "script", "interpreter", "args", "watch", "time", "env"}


def _env_text(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return "" if value is None else str(value)


def _changes(before: dict, app: dict) -> dict:
    """폼 값 중 실제로 바뀐 속성만. 값이 None 이면 그 속성을 지운다."""
    changes: dict = {}
    if before.get("name") != app["name"]:
        changes["name"] = app["name"]
    cwd = str(before.get("cwd") or "")
    if not cwd or Path(os.path.expanduser(cwd)).resolve() != Path(app["cwd"]):
        changes["cwd"] = app["cwd"]
    if before.get("script") != app["script"]:
        changes["script"] = app["script"]
    if (before.get("interpreter") or "") != app.get("interpreter", ""):
        changes["interpreter"] = app.get("interpreter")
    if _args_text(before.get("args")) != app.get("args", ""):
        changes["args"] = app.get("args")
    for flag in ("watch", "time"):
        if bool(before.get(flag)) != app[flag]:
            changes[flag] = app[flag]
    env = before.get("env") if isinstance(before.get("env"), dict) else {}
    if {key: _env_text(value) for key, value in env.items()} != app.get("env", {}):
        changes["env"] = app.get("env")
    return changes


def update_app(name: str, data: dict, path: Path | None = None) -> dict:
    """name 앱의 속성 중 폼에서 바뀐 것만 고친다."""
    path = path or ecosystem_path()
    app = build_app(data)
    with _lock:
        apps = _load_full(path)
        index = _find(apps, name)
        before = apps[index]
        if app["name"] != name and any(
            isinstance(other, dict) and other.get("name") == app["name"]
            for other in apps
        ):
            raise ValueError(f"'{app['name']}' 앱이 이미 ecosystem 파일에 있습니다.")
        if "env" in before and not isinstance(before["env"], dict):
            raise EcosystemError("env 값이 객체가 아니라 자동으로 고칠 수 없습니다.")
        changes = _changes(before, app)
        if not changes:
            return {"app": app, "changed": [], "backup": None, "path": str(path)}

        source = path.read_text(encoding="utf-8")
        masked = _mask_code(source, "s")
        begin, stop, _ = _app_elements(source, masked, len(apps))[index]
        props = _props(source, masked, begin, stop)
        multiline = "\n" in source[begin:stop]
        first = next(iter(props.values()))
        indent = _indent_of(source, first["start"]) if multiline else None
        object_indent = _indent_of(source, begin) or ""
        step = (indent or "")[len(object_indent) :] or "  "

        edits, added = [], []
        removed = [
            key
            for key, value in changes.items()
            if value in (None, "", {}) and key in props
        ]
        for key, value in changes.items():
            if key in removed:
                continue
            if value in (None, "", {}):
                continue  # 원래 없던 속성을 비운 경우
            if key in props:
                prop = props[key]
                prop_multiline = "\n" in source[prop["value_start"] : prop["value_end"]]
                prop_indent = _indent_of(source, prop["start"]) or ""
                edits.append(
                    (
                        prop["value_start"],
                        prop["value_end"],
                        _literal(value, prop_indent, step, prop_multiline),
                    )
                )
            else:
                added.append((key, value))
        for key in removed:
            prop = props[key]
            edits.append(
                _removal(source, (prop["start"], prop["value_end"], prop["comma"]))
            )
        if added:
            remaining = [k for k in props if k not in removed]
            if not remaining:
                raise EcosystemError(
                    "항목을 고칠 수 없습니다. 파일을 직접 수정해 주시기 바랍니다."
                )
            last = props[remaining[-1]]
            if multiline and indent is not None:
                text = "".join(
                    f"\n{indent}{key}: {_literal(value, indent, step, True)},"
                    for key, value in added
                )
                # 마지막 속성 줄 끝(뒤따르는 주석 뒤)에 새 줄로 붙인다
                after = (
                    last["value_end"] if last["comma"] is None else last["comma"] + 1
                )
                line_end = source.find("\n", after)
                line_end = len(source) if line_end < 0 else line_end
                at = line_end if not masked[after:line_end].strip() else after
                if last["comma"] is None:
                    text = text[:-1]
                    if at == last["value_end"]:
                        text = "," + text
                    else:
                        edits.append((last["value_end"], last["value_end"], ","))
                edits.append((at, at, text))
            else:
                text = "".join(
                    f", {key}: {_literal(value, '', step, False)}"
                    for key, value in added
                )
                edits.append((last["value_end"], last["value_end"], text))
        new_source = _apply(source, edits)

        expected = json.loads(json.dumps(apps))
        target = expected[index]
        for key, value in changes.items():
            if value in (None, "", {}):
                target.pop(key, None)
            else:
                target[key] = value
        backup = _save(path, new_source, lambda temp: _load_full(temp) == expected)
    return {"app": app, "changed": sorted(changes), "backup": backup, "path": str(path)}


def delete_app(name: str, path: Path | None = None) -> dict:
    path = path or ecosystem_path()
    with _lock:
        apps = _load_full(path)
        index = _find(apps, name)
        source = path.read_text(encoding="utf-8")
        masked = _mask_code(source, "s")
        elements = _app_elements(source, masked, len(apps))
        new_source = _apply(source, [_removal(source, elements[index])])
        expected = json.loads(json.dumps(apps[:index] + apps[index + 1 :]))
        backup = _save(path, new_source, lambda temp: _load_full(temp) == expected)
    return {"backup": backup, "path": str(path)}


def start_app(name: str, path: Path | None = None) -> tuple[bool, str]:
    path = path or ecosystem_path()
    if not APP_NAME.match(name or ""):
        raise ValueError("잘못된 앱 이름입니다.")
    if not any(app.get("name") == name for app in load_apps(path)):
        raise KeyError("ecosystem 파일에 없는 앱입니다.")
    pm2 = shutil.which("pm2")
    if not pm2:
        raise EcosystemError("pm2 를 찾을 수 없습니다.")
    try:
        result = subprocess.run(
            [pm2, "start", str(path), "--only", name],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            cwd=str(path.parent),
            env=child_env(),
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise EcosystemError("pm2 start 를 실행하지 못했습니다.") from error
    output = re.sub(r"\x1b\[[0-9;]*m", "", (result.stdout + result.stderr).strip())
    return result.returncode == 0, output[-4000:]
