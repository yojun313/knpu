#!/usr/bin/python3 -I
"""Nginx 도메인을 root 로 바꾸는 유일한 통로. 대시보드는 sudo 로 이 프로그램만 실행할 수 있다.

설치하면 root 소유로 /usr/local/sbin/knpu-nginx 에 복사된다 (admin/scripts/install_nginx_helper.sh).
저장소의 이 파일을 고쳐도 다시 설치하기 전에는 root 로 실행되지 않는다.

- 설정 파일 내용을 입력으로 받지 않는다. nginx 설정을 마음대로 쓸 수 있으면 곧 root 권한이므로,
  검증된 도메인 · 경로 · 포트 · 이메일만 받아 설정을 여기서 직접 만든다.
- 다른 프로그램은 절대 경로로, 셸 없이, 비운 환경 변수로 실행한다.
- nginx -t 가 실패하면 원래 설정으로 되돌리고 reload 하지 않는다.
- 표준 라이브러리만 쓰고 파일 경로 · 동작을 바꾸는 옵션이나 환경 변수를 받지 않는다.
- Domains 페이지는 관리자 로그인으로 보호하므로 변경 비밀번호는 쓰지 않는다(REQUIRE_PASSPHRASE).
"""

import fcntl
import getpass
import hashlib
import hmac
import json
import os
import re
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time

SITES_AVAILABLE = "/etc/nginx/sites-available"
SITES_ENABLED = "/etc/nginx/sites-enabled"
NGINX = "/usr/sbin/nginx"
CERTBOT = "/usr/bin/certbot"
SYSTEMCTL = "/usr/bin/systemctl"
REJECT_CONF = "/etc/nginx/conf.d/reject-unknown-host.conf"
BACKUP_ROOT = "/var/backups/nginx-helper"
REQUIRE_PASSPHRASE = False
PASSPHRASE_FILE = "/etc/knpu-nginx/passphrase"
FAILURES_FILE = "/run/knpu-nginx-failures"
MAX_FAILURES = 5
LOCK_SECONDS = 15 * 60
MAX_PASSPHRASE = 1024

EXIT_FAILED = 1
EXIT_LAST_PATH = 3
EXIT_PASSPHRASE = 4

COMMAND_TIMEOUT = 60
CERTBOT_TIMEOUT = 300

_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_DOMAIN = re.compile(rf"{_LABEL}(?:\.{_LABEL})+")
_PATH_SEGMENT = re.compile(r"[A-Za-z0-9_-]+")
_EMAIL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PORT = re.compile(r"[0-9]{1,5}")
_LOCATION = re.compile(r"^[ \t]*location\s+(\S+)\s*\{", re.MULTILINE)
# 클라이언트가 보낸 값을 그대로 넘기면 uvicorn 등이 믿어 버려 IP 를 속일 수 있다 → nginx 가 항상 덮어쓴다
FORWARDED_HEADERS = (
    "proxy_set_header X-Real-IP $remote_addr;",
    "proxy_set_header X-Forwarded-For $remote_addr;",
    "proxy_set_header X-Forwarded-Proto $scheme;",
)
_FORWARDED_LINE = re.compile(
    r"^[ \t]*proxy_set_header\s+(?:X-Real-IP|X-Forwarded-For|X-Forwarded-Proto)\s[^;]*;[^\n]*\n",
    re.MULTILINE | re.IGNORECASE,
)
_PROXY_PASS_LINE = re.compile(r"^[ \t]*proxy_pass\s[^;]*;[^\n]*\n", re.MULTILINE)
REJECT_CONTENT = """# 등록되지 않은 도메인으로 온 HTTPS 요청은 받지 않는다 (없으면 알파벳순 첫 사이트로 넘어간다)
server {
    listen 443 ssl default_server;
    ssl_reject_handshake on;
    return 444;
}
"""
_SERVER_NAME = re.compile(r"^[^#\n]*?(?<![\w-])server_name\s+([^;]+);", re.MULTILINE)


class HelperError(Exception):
    def __init__(self, message, code=EXIT_FAILED):
        super().__init__(message)
        self.code = code


# ── 검증 ──────────────────────────────────────────────────────────────
# fullmatch 를 쓴다. `$` 는 끝의 줄바꿈을 통과시켜 nginx 설정에 줄을 끼워 넣을 수 있다.
def is_valid_domain(domain):
    return (
        isinstance(domain, str)
        and len(domain) <= 253
        and bool(_DOMAIN.fullmatch(domain))
    )


def is_valid_port(port):
    return (
        isinstance(port, str)
        and bool(_PORT.fullmatch(port))
        and 1 <= int(port) <= 65535
    )


def is_valid_email(email):
    return (
        isinstance(email, str) and len(email) <= 254 and bool(_EMAIL.fullmatch(email))
    )


def normalize_path(path):
    """`/`, `/api`, `/a/b` 형태로 맞춘다. 허용하지 않는 글자가 있으면 None."""
    if not isinstance(path, str) or len(path) > 200:
        return None
    path = path.strip()
    if path in ("", "/"):
        return "/"
    segments = [segment for segment in path.split("/") if segment]
    if not segments or not all(_PATH_SEGMENT.fullmatch(s) for s in segments):
        return None
    return "/" + "/".join(segments)


def _need_domain(domain):
    if not is_valid_domain(domain):
        raise HelperError("유효하지 않은 도메인입니다.")


def _need_port(port):
    if not is_valid_port(port):
        raise HelperError("유효하지 않은 포트입니다.")


def _need_email(email):
    if not is_valid_email(email):
        raise HelperError("유효하지 않은 이메일입니다.")


def _need_path(path):
    normalized = normalize_path(path)
    if normalized is None:
        raise HelperError("유효하지 않은 경로입니다.")
    return normalized


# ── 설정 읽기 · 만들기 (파일을 건드리지 않는다) ────────────────────────
def extract_locations(content):
    results = []
    for match in _LOCATION.finditer(content):
        raw_path = match.group(1)
        depth = 1
        index = match.end()
        while index < len(content) and depth > 0:
            if content[index] == "{":
                depth += 1
            elif content[index] == "}":
                depth -= 1
            index += 1
        block = content[match.end() : index - 1]
        port = re.search(r"proxy_pass\s+http://localhost:(\d+)", block)
        results.append(
            {
                "path": "/" if raw_path == "/" else raw_path.rstrip("/"),
                "port": port.group(1) if port else "N/A",
                "start": match.start(),
                "end": index,
            }
        )
    return results


def first_server_name(content):
    match = _SERVER_NAME.search(content)
    return match.group(1).strip() if match else None


def location_block(path, port):
    # 전달 헤더는 proxy_pass 바로 아래에 둔다 (hardened_config 와 같은 모양이어야 다시 고칠 일이 없다)
    forwarded = "".join(f"        {line}\n" for line in FORWARDED_HEADERS)
    common = (
        "        proxy_http_version 1.1;\n"
        "        proxy_set_header Upgrade $http_upgrade;\n"
        "        proxy_set_header Connection 'upgrade';\n"
        "        proxy_set_header Host $host;\n"
        "        proxy_cache_bypass $http_upgrade;\n"
        "    }\n"
    )
    if path == "/":
        return (
            "    location / {\n"
            f"        proxy_pass http://localhost:{port};\n{forwarded}{common}"
        )
    return (
        f"    location {path}/ {{\n"
        f"        proxy_pass http://localhost:{port}/;\n{forwarded}"
        f"        proxy_redirect / {path}/;\n{common}"
    )


def new_config(domain, blocks):
    body = "\n".join(blocks)
    return f"server {{\n    listen 80;\n    server_name {domain};\n\n{body}}}\n"


def hardened_config(content):
    """모든 proxy_pass location 이 전달 헤더를 덮어쓰게 한다. 다시 돌려도 결과가 같다."""
    result = []
    position = 0
    for item in extract_locations(content):
        block = content[item["start"] : item["end"]]
        if "proxy_pass" not in block:
            continue
        cleaned = _FORWARDED_LINE.sub("", block)
        line = _PROXY_PASS_LINE.search(cleaned)
        if line is None:
            continue
        headers = "".join(f"        {header}\n" for header in FORWARDED_HEADERS)
        result.append(content[position : item["start"]])
        result.append(cleaned[: line.end()] + headers + cleaned[line.end() :])
        position = item["end"]
    result.append(content[position:])
    return "".join(result)


def needs_hardening(content):
    return hardened_config(content) != content


def with_path_added(content, path, port):
    locations = extract_locations(content)
    if any(location["path"] == path for location in locations):
        raise HelperError("이미 존재하는 경로입니다.")
    block = location_block(path, port)
    if locations:
        at = locations[-1]["end"]
        return content[:at] + "\n" + block + content[at:]
    name = _SERVER_NAME.search(content)
    if not name:
        raise HelperError("설정 파일 형식을 인식할 수 없습니다.")
    return content[: name.end()] + "\n\n" + block + content[name.end() :]


def _find_location(content, path):
    locations = extract_locations(content)
    target = next((item for item in locations if item["path"] == path), None)
    if target is None:
        raise HelperError("해당 경로를 찾을 수 없습니다.")
    return locations, target


def with_port_changed(content, path, port):
    _, target = _find_location(content, path)
    block, count = re.subn(
        r"(proxy_pass\s+http://localhost:)\d+",
        rf"\g<1>{port}",
        content[target["start"] : target["end"]],
        count=1,
    )
    if not count:
        raise HelperError("포트 설정을 찾을 수 없습니다.")
    return content[: target["start"]] + block + content[target["end"] :]


def with_path_removed(content, path):
    locations, target = _find_location(content, path)
    if len(locations) <= 1:
        raise HelperError(
            "마지막 경로입니다. 도메인 전체 삭제가 필요합니다.", EXIT_LAST_PATH
        )
    start, end = target["start"], target["end"]
    while start > 0 and content[start - 1] in " \t":
        start -= 1
    if start > 0 and content[start - 1] == "\n":
        start -= 1
    return content[:start] + content[end:]


def renamed_config(content, new_domain):
    """경로 · 포트만 옮긴 HTTP 설정. 옛 인증서를 가리키는 줄은 버리고 새 인증서는 certbot 이 붙인다."""
    blocks = [
        location_block(item["path"], item["port"])
        for item in extract_locations(content)
        if item["port"] != "N/A"
    ]
    if not blocks:
        raise HelperError("옮길 수 있는 경로(proxy_pass)를 찾지 못했습니다.")
    return new_config(new_domain, blocks)


# ── 실행 ──────────────────────────────────────────────────────────────
def _emit(text):
    # 대시보드가 재시작돼 파이프가 끊겨도 작업은 끝까지 마치고 정리해야 한다
    try:
        print(text, flush=True)
    except (OSError, ValueError):
        pass


def _run(command, timeout=COMMAND_TIMEOUT):
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd="/",
    )
    timer = threading.Timer(timeout, process.kill)
    timer.start()
    try:
        with process.stdout:
            for line in process.stdout:
                _emit(line.rstrip())
        code = process.wait()
    finally:
        timer.cancel()
    if code != 0:
        raise HelperError(
            f"{os.path.basename(command[0])} 실행 실패 (종료 코드 {code})"
        )


def _test_config():
    _run([NGINX, "-t"])


def _reload():
    _run([SYSTEMCTL, "reload", "nginx"])


def _certbot_issue(domain, email):
    _run(
        [
            CERTBOT,
            "--nginx",
            "-d",
            domain,
            "--non-interactive",
            "--agree-tos",
            "-m",
            email,
        ],
        CERTBOT_TIMEOUT,
    )


def _certbot_delete(domain):
    try:
        _run(
            [CERTBOT, "delete", "--cert-name", domain, "--non-interactive"],
            CERTBOT_TIMEOUT,
        )
    except HelperError:
        _emit("(인증서가 없거나 이미 삭제되었습니다. 계속합니다.)")


def _available(domain):
    return os.path.join(SITES_AVAILABLE, domain)


def _enabled(domain):
    return os.path.join(SITES_ENABLED, domain)


def _read_config(domain):
    path = _available(domain)
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        raise HelperError("해당 도메인이 존재하지 않습니다.") from None
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid():
        raise HelperError(
            "설정 파일이 일반 파일이 아니거나 소유자가 달라 건드리지 않습니다."
        )
    with open(path, encoding="utf-8", errors="surrogateescape") as handle:
        return handle.read()


def _write_config(path, content):
    fd, temp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".nginx-helper-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", errors="surrogateescape") as handle:
            handle.write(content)
        os.chmod(temp, 0o644)
        os.replace(temp, path)
    except BaseException:
        if os.path.lexists(temp):
            os.unlink(temp)
        raise


def _ensure_free(domain):
    """이미 쓰는 이름이면 멈춘다. 다른 설정 파일에 같은 server_name 이 있어도 가로채지 않는다."""
    if os.path.lexists(_available(domain)) or os.path.lexists(_enabled(domain)):
        raise HelperError("이미 존재하는 도메인입니다.")
    for name in os.listdir(SITES_AVAILABLE):
        path = os.path.join(SITES_AVAILABLE, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8", errors="replace") as handle:
            names = _SERVER_NAME.findall(handle.read())
        if any(domain in value.split() for value in names):
            raise HelperError(f"{name} 설정이 이미 이 도메인을 쓰고 있습니다.")


def _unlink(path):
    if os.path.lexists(path):
        os.unlink(path)


def _replace_config(domain, content):
    original = _read_config(domain)
    path = _available(domain)
    _emit(f"[1/3] 설정 갱신: {domain}")
    _write_config(path, content)
    try:
        _emit("[2/3] 설정 검사")
        _test_config()
        _emit("[3/3] nginx reload")
        _reload()
    except HelperError:
        _emit("실패해서 원래 설정으로 되돌립니다.")
        _write_config(path, original)
        raise


def _quiet_restore_reload():
    try:
        _test_config()
        _reload()
    except HelperError as error:
        _emit(f"경고: 되돌린 뒤 reload 실패: {error}")


def _managed_sites():
    return sorted(
        name
        for name in os.listdir(SITES_AVAILABLE)
        if is_valid_domain(name) and os.path.isfile(_available(name))
    )


def cmd_harden():
    """이미 있는 사이트에 전달 헤더를 넣고 모르는 도메인의 HTTPS 를 막는다. 실패하면 전부 되돌린다."""
    originals = {name: _read_config(name) for name in _managed_sites()}
    changed = {
        name: new
        for name, old in originals.items()
        if (new := hardened_config(old)) != old
    }
    conf_exists = os.path.lexists(REJECT_CONF)
    if not changed and conf_exists:
        _emit("이미 모두 적용되어 있습니다.")
        return
    backup = os.path.join(BACKUP_ROOT, time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(backup, mode=0o700, exist_ok=True)
    for name in changed:
        _write_config(os.path.join(backup, name), originals[name])
    _emit(f"[1/3] 사이트 {len(changed)}개 갱신 (백업: {backup})")
    try:
        for name, content in changed.items():
            _write_config(_available(name), content)
        if not conf_exists:
            _write_config(REJECT_CONF, REJECT_CONTENT)
        _emit("[2/3] 설정 검사")
        _test_config()
        _emit("[3/3] nginx reload")
        _reload()
    except (HelperError, OSError):
        _emit("실패해서 전부 원래대로 되돌립니다.")
        for name in changed:
            _write_config(_available(name), originals[name])
        if not conf_exists:
            _unlink(REJECT_CONF)
        raise
    _emit("적용했습니다.")


def cmd_add(domain, email, port, path):
    _need_domain(domain)
    _need_email(email)
    _need_port(port)
    path = _need_path(path)
    _ensure_free(domain)
    _emit(f"[1/4] 설정 작성: {domain}{'' if path == '/' else path} -> localhost:{port}")
    _write_config(_available(domain), new_config(domain, [location_block(path, port)]))
    os.symlink(_available(domain), _enabled(domain))
    try:
        _emit("[2/4] 설정 검사")
        _test_config()
        _emit("[3/4] nginx reload")
        _reload()
        _emit("[4/4] SSL 인증서 발급 (시간이 걸릴 수 있어요)")
        _certbot_issue(domain, email)
    except HelperError:
        _emit("실패해서 새 설정을 지웁니다.")
        _unlink(_enabled(domain))
        _unlink(_available(domain))
        _quiet_restore_reload()
        raise
    _emit(f"완료: https://{domain}")


def cmd_add_path(domain, path, port):
    _need_domain(domain)
    path = _need_path(path)
    _need_port(port)
    _replace_config(domain, with_path_added(_read_config(domain), path, port))
    _emit("경로를 추가했습니다.")


def cmd_edit_path(domain, path, port):
    _need_domain(domain)
    path = _need_path(path)
    _need_port(port)
    _replace_config(domain, with_port_changed(_read_config(domain), path, port))
    _emit("포트를 수정했습니다.")


def cmd_delete_path(domain, path):
    _need_domain(domain)
    path = _need_path(path)
    _replace_config(domain, with_path_removed(_read_config(domain), path))
    _emit("경로를 삭제했습니다.")


def cmd_rename(old_domain, new_domain, email):
    _need_domain(old_domain)
    _need_domain(new_domain)
    _need_email(email)
    if old_domain == new_domain:
        raise HelperError("기존 도메인과 새 도메인이 같습니다.")
    _ensure_free(new_domain)
    original = _read_config(old_domain)
    config = renamed_config(original, new_domain)
    was_enabled = os.path.lexists(_enabled(old_domain))

    _emit(f"[1/5] 새 설정 작성: {old_domain} -> {new_domain} (경로 · 포트 유지)")
    _write_config(_available(new_domain), config)
    os.symlink(_available(new_domain), _enabled(new_domain))
    _emit("[2/5] 기존 설정 제거")
    _unlink(_enabled(old_domain))
    _unlink(_available(old_domain))
    try:
        _emit("[3/5] 설정 검사 · nginx reload")
        _test_config()
        _reload()
        _emit(f"[4/5] SSL 인증서 발급: {new_domain} (DNS 가 이 서버를 가리켜야 해요)")
        _certbot_issue(new_domain, email)
    except HelperError:
        _emit(f"실패해서 원래 설정으로 되돌립니다: {old_domain}")
        _unlink(_enabled(new_domain))
        _unlink(_available(new_domain))
        _write_config(_available(old_domain), original)
        if was_enabled:
            os.symlink(_available(old_domain), _enabled(old_domain))
        _quiet_restore_reload()
        raise
    _emit(f"[5/5] 기존 인증서 정리: {old_domain}")
    _certbot_delete(old_domain)
    _emit(f"완료: https://{new_domain}")


def cmd_delete(domain):
    _need_domain(domain)
    original = _read_config(domain)
    was_enabled = os.path.lexists(_enabled(domain))
    _emit(f"[1/3] 설정 제거: {domain}")
    _unlink(_enabled(domain))
    _unlink(_available(domain))
    try:
        _emit("[2/3] 설정 검사 · nginx reload")
        _test_config()
        _reload()
    except HelperError:
        _emit("실패해서 원래 설정으로 되돌립니다.")
        _write_config(_available(domain), original)
        if was_enabled:
            os.symlink(_available(domain), _enabled(domain))
        raise
    _emit("[3/3] 인증서 삭제")
    _certbot_delete(domain)
    _emit(f"{domain} 삭제 완료")


COMMANDS = {
    "add": (cmd_add, 4),
    "add-path": (cmd_add_path, 3),
    "edit-path": (cmd_edit_path, 3),
    "delete-path": (cmd_delete_path, 2),
    "rename": (cmd_rename, 3),
    "delete": (cmd_delete, 1),
    "harden": (cmd_harden, 0),
}


# ── 변경 비밀번호 ─────────────────────────────────────────────────────
def _read_passphrase():
    if sys.stdin is not None and sys.stdin.isatty():
        return getpass.getpass("변경 비밀번호: ")
    line = sys.stdin.buffer.readline(MAX_PASSPHRASE + 1)
    return line.decode("utf-8", "replace").rstrip("\n")


def _load_failures():
    try:
        with open(FAILURES_FILE, encoding="utf-8") as handle:
            data = json.load(handle)
        return int(data["count"]), float(data["until"])
    except (OSError, ValueError, KeyError, TypeError):
        return 0, 0.0


def _save_failures(count, until):
    _write_private(FAILURES_FILE, json.dumps({"count": count, "until": until}))


def _write_private(path, content):
    fd, temp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".nginx-helper-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(temp, path)
    except BaseException:
        if os.path.lexists(temp):
            os.unlink(temp)
        raise


def _passphrase_matches(passphrase):
    try:
        info = os.stat(PASSPHRASE_FILE)
        if info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise HelperError("변경 비밀번호 파일의 권한이 안전하지 않습니다.")
        with open(PASSPHRASE_FILE, encoding="ascii") as handle:
            kind, cost, salt, stored = handle.read().strip().split("$")
        if kind != "scrypt":
            raise ValueError
        derived = hashlib.scrypt(
            passphrase.encode("utf-8", "surrogateescape"),
            salt=bytes.fromhex(salt),
            n=2 ** int(cost),
            r=8,
            p=1,
            maxmem=256 * 1024 * 1024,
        )
    except (OSError, ValueError) as error:
        raise HelperError(
            "변경 비밀번호가 설정되어 있지 않습니다. 설치 스크립트를 다시 실행해 주세요."
        ) from error
    return hmac.compare_digest(derived.hex(), stored)


def _authorize():
    """비밀번호를 확인한다. 틀리면 5번까지만 받고 15분 잠근다."""
    if not REQUIRE_PASSPHRASE:
        return
    count, until = _load_failures()
    if until > time.time():
        raise HelperError(
            "변경 비밀번호를 여러 번 틀려 잠겼습니다. 15분 뒤 다시 해 주세요.",
            EXIT_PASSPHRASE,
        )
    if _passphrase_matches(_read_passphrase()):
        if count:
            _save_failures(0, 0.0)
        return
    count += 1
    if count >= MAX_FAILURES:
        _save_failures(0, time.time() + LOCK_SECONDS)
    else:
        _save_failures(count, 0.0)
    raise HelperError("변경 비밀번호가 틀렸습니다.", EXIT_PASSPHRASE)


def run(argv, on_authorized=None):
    if argv == ["check"]:
        return 0
    spec = COMMANDS.get(argv[0]) if argv else None
    if spec is None or len(argv) - 1 != spec[1]:
        _emit("실패: 지원하지 않는 명령입니다.")
        return EXIT_FAILED
    try:
        _authorize()
    except HelperError as error:
        _emit(f"실패: {error}")
        return error.code
    if on_authorized:
        on_authorized()
    lock = os.open(SITES_AVAILABLE, os.O_RDONLY | os.O_DIRECTORY)
    try:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            _emit("실패: 다른 도메인 작업이 진행 중입니다. 잠시 뒤 다시 해 주세요.")
            return EXIT_FAILED
        try:
            spec[0](*argv[1:])
        except HelperError as error:
            _emit(f"실패: {error}")
            return error.code
        except (OSError, subprocess.SubprocessError) as error:
            _emit(f"실패: {error}")
            return EXIT_FAILED
        return 0
    finally:
        os.close(lock)


def main():
    if os.geteuid() != 0:
        print("root 로 실행해야 합니다.", file=sys.stderr)
        return EXIT_FAILED
    os.environ.clear()
    os.environ.update(
        PATH="/usr/sbin:/usr/bin:/sbin:/bin", LC_ALL="C.UTF-8", HOME="/root"
    )
    os.umask(0o022)
    os.chdir("/")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

    def keep_running():
        # 끊겨도 되돌리기까지 마치도록 시작한 작업은 끝까지 돈다
        for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(number, signal.SIG_IGN)

    return run(sys.argv[1:], keep_running)


if __name__ == "__main__":
    sys.exit(main())
