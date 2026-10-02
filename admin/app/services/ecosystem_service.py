"""PM2 ecosystem.config.js 읽기 · 앱 추가.

- 읽기: pm2 와 같은 방식으로 node 가 파일을 require 해서 JSON 으로 돌려준다.
- 추가: 파일 전체를 다시 쓰지 않고 `apps: [ ... ]` 의 닫는 `]` 바로 앞에 새 항목만 끼워 넣어
  기존 서식 · 주석 · 함수 값을 그대로 둔다. 쓰기 전에 node 로 다시 읽어 검증하고,
  원본은 백업한 뒤 원자적으로 교체한다.
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


def _mask_code(source: str) -> str:
    """문자열 · 템플릿 문자열 · 주석을 같은 길이의 공백으로 가린다 (위치는 그대로)."""
    out = list(source)
    index, length = 0, len(source)
    while index < length:
        char = source[index]
        if char in "\"'`":
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
                out[position] = " "
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
        raise ValueError("실행 파일(script)을 입력하세요.")
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

        directory = path.parent
        fd, temp_name = tempfile.mkstemp(
            dir=directory, prefix=".ecosystem.", suffix=".js"
        )
        temp = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(new_source)
            if path.exists():
                os.chmod(temp, path.stat().st_mode & 0o777)
            # 쓰기 전에 node 로 다시 읽어 기존 앱 + 새 앱이 그대로 나오는지 확인한다.
            verified = load_apps(temp)
            if [a.get("name") for a in verified] != [
                a.get("name") for a in existing
            ] + [app["name"]]:
                raise EcosystemError(
                    "수정한 ecosystem 파일을 검증하지 못해 저장하지 않았습니다."
                )
            backup = None
            if path.exists():
                backup = path.with_name(
                    f"{path.name}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
                )
                shutil.copy2(path, backup)
            os.replace(temp, path)
        except BaseException:
            temp.unlink(missing_ok=True)
            raise
    return {"app": app, "backup": str(backup) if backup else None, "path": str(path)}


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
