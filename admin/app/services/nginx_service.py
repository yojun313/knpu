"""nginx 도메인 읽기와 root 헬퍼 호출.

설정 파일은 직접 읽고, 바꾸는 일은 모두 nginx_helper.py (설치본 /usr/local/sbin/knpu-nginx) 에 맡긴다.
일반 사용자가 고칠 수 있는 스크립트를 sudo 로 실행하면 웹 프로세스가 곧 root 이므로 그렇게 하지 않는다.
"""

import os
import subprocess

from app.services import nginx_helper

HELPER_PATH = "/usr/local/sbin/knpu-nginx"
SUDO = "/usr/bin/sudo"
HELPER_TIMEOUT = 90
HELPER_MISSING = (
    "Nginx 헬퍼가 설치되어 있지 않습니다. "
    "서버에서 sudo bash admin/scripts/install_nginx_helper.sh <계정> 을 실행해 주세요."
)


class NginxService:
    SITES_AVAILABLE = nginx_helper.SITES_AVAILABLE
    SITES_ENABLED = nginx_helper.SITES_ENABLED

    # ---------- validation / normalization ----------

    is_valid_domain = staticmethod(nginx_helper.is_valid_domain)
    is_valid_port = staticmethod(nginx_helper.is_valid_port)
    is_valid_email = staticmethod(nginx_helper.is_valid_email)
    normalize_path = staticmethod(nginx_helper.normalize_path)

    # ---------- read ----------

    @classmethod
    def get_domains(cls):
        domains = []
        if not os.path.exists(cls.SITES_ENABLED):
            return domains

        for filename in os.listdir(cls.SITES_ENABLED):
            file_path = os.path.join(cls.SITES_ENABLED, filename)
            if not os.path.isfile(file_path):
                continue
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except OSError:
                continue
            domain = nginx_helper.first_server_name(content)
            if not cls.is_valid_domain(domain):
                continue
            paths = [
                {"path": loc["path"], "port": loc["port"]}
                for loc in nginx_helper.extract_locations(content)
            ]
            domains.append(
                {
                    "domain": domain,
                    "filename": filename,
                    "paths": paths,
                    "primary_port": cls._primary_port(paths),
                }
            )

        domains.sort(
            key=lambda d: (
                d["primary_port"] is None,
                d["primary_port"] or 0,
                d["domain"],
            )
        )
        return domains

    @staticmethod
    def _primary_port(paths):
        if not paths:
            return None
        root = next((p for p in paths if p["path"] == "/"), None)
        candidates = [root] if root else paths
        ports = []
        for p in candidates:
            try:
                ports.append(int(p["port"]))
            except (TypeError, ValueError):
                continue
        return min(ports) if ports else None

    # ---------- helper ----------

    @staticmethod
    def helper_installed() -> bool:
        return os.path.isfile(HELPER_PATH)

    @staticmethod
    def helper_command(*args: str) -> list[str]:
        return [SUDO, "-n", HELPER_PATH, *args]

    @classmethod
    def _run_helper(cls, *args: str) -> tuple[int, str]:
        if not cls.helper_installed():
            return 1, f"실패: {HELPER_MISSING}"
        try:
            result = subprocess.run(
                cls.helper_command(*args),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=HELPER_TIMEOUT,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return 1, "실패: 시간 안에 끝나지 않았습니다."
        return result.returncode, (result.stdout + result.stderr).strip()

    @staticmethod
    def _message(output: str) -> str:
        lines = [line for line in output.splitlines() if line.strip()]
        failed = [line for line in lines if line.startswith("실패: ")]
        if failed:
            return failed[-1].removeprefix("실패: ")
        return lines[-1] if lines else "작업에 실패했습니다."

    # ---------- write (existing domain, no certbot) ----------

    @classmethod
    def add_path(cls, domain: str, path: str, port: str):
        code, output = cls._run_helper("add-path", domain, path, port)
        return code == 0, cls._message(output)

    @classmethod
    def edit_path_port(cls, domain: str, path: str, port: str):
        code, output = cls._run_helper("edit-path", domain, path, port)
        return code == 0, cls._message(output)

    @classmethod
    def delete_path(cls, domain: str, path: str):
        code, output = cls._run_helper("delete-path", domain, path)
        last = code == nginx_helper.EXIT_LAST_PATH
        return code == 0, cls._message(output), last

    # ---------- domain rename (미리 검사만. 실제 변경은 헬퍼가 다시 판단한다) ----------

    @classmethod
    def check_rename(cls, old_domain: str, new_domain: str):
        if not cls.is_valid_domain(old_domain):
            return False, "유효하지 않은 기존 도메인입니다."
        if not cls.is_valid_domain(new_domain):
            return False, "유효하지 않은 새 도메인입니다."
        if old_domain == new_domain:
            return False, "기존 도메인과 새 도메인이 같습니다."
        old_path = os.path.join(cls.SITES_AVAILABLE, old_domain)
        if not os.path.exists(old_path):
            return False, "해당 도메인이 존재하지 않습니다."
        if os.path.lexists(os.path.join(cls.SITES_AVAILABLE, new_domain)):
            return False, "이미 존재하는 도메인입니다."
        with open(old_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        try:
            nginx_helper.renamed_config(content, new_domain)
        except nginx_helper.HelperError as error:
            return False, str(error)
        return True, ""
