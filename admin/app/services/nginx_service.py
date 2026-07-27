import subprocess
import os
import re

DOMAIN_RE = re.compile(
    r"^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)
PATH_SEGMENT_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
LOCATION_START_RE = re.compile(r"location\s+(\S+)\s*\{")


class NginxService:
    SCRIPT_DIR = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "scripts")
    )
    SITES_AVAILABLE = "/etc/nginx/sites-available"
    SITES_ENABLED = "/etc/nginx/sites-enabled"

    # ---------- validation / normalization ----------

    @staticmethod
    def is_valid_domain(domain: str) -> bool:
        return bool(domain) and bool(DOMAIN_RE.match(domain))

    @staticmethod
    def normalize_path(path: str) -> str:
        if path is None:
            return None
        path = path.strip()
        if path in ("", "/"):
            return "/"
        segments = [seg for seg in path.split("/") if seg]
        if not segments:
            return None
        for seg in segments:
            if not PATH_SEGMENT_RE.match(seg):
                return None
        return "/" + "/".join(segments)

    # ---------- location block parsing ----------

    @classmethod
    def _extract_locations(cls, content: str):
        results = []
        for m in LOCATION_START_RE.finditer(content):
            raw_path = m.group(1)
            depth = 1
            i = m.end()
            while i < len(content) and depth > 0:
                if content[i] == "{":
                    depth += 1
                elif content[i] == "}":
                    depth -= 1
                i += 1
            block = content[m.end() : i - 1]
            port_match = re.search(r"proxy_pass\s+http://localhost:(\d+)", block)
            path = "/" if raw_path == "/" else raw_path.rstrip("/")
            results.append(
                {
                    "path": path,
                    "port": port_match.group(1) if port_match else "N/A",
                    "start": m.start(),
                    "end": i,
                }
            )
        return results

    @staticmethod
    def _build_location_block(path: str, port: str) -> str:
        if path == "/":
            return (
                "    location / {\n"
                f"        proxy_pass http://localhost:{port};\n"
                "        proxy_http_version 1.1;\n"
                "        proxy_set_header Upgrade $http_upgrade;\n"
                "        proxy_set_header Connection 'upgrade';\n"
                "        proxy_set_header Host $host;\n"
                "        proxy_cache_bypass $http_upgrade;\n"
                "    }\n"
            )
        return (
            f"    location {path}/ {{\n"
            f"        proxy_pass http://localhost:{port}/;\n"
            f"        proxy_redirect / {path}/;\n"
            "        proxy_http_version 1.1;\n"
            "        proxy_set_header Upgrade $http_upgrade;\n"
            "        proxy_set_header Connection 'upgrade';\n"
            "        proxy_set_header Host $host;\n"
            "        proxy_cache_bypass $http_upgrade;\n"
            "    }\n"
        )

    # ---------- read ----------

    @classmethod
    def get_domains(cls):
        domains = []

        if not os.path.exists(cls.SITES_ENABLED):
            return domains

        for filename in os.listdir(cls.SITES_ENABLED):
            file_path = os.path.join(cls.SITES_ENABLED, filename)
            if os.path.isfile(file_path):
                try:
                    with open(file_path, "r") as f:
                        content = f.read()

                    domain_match = re.search(r"server_name\s+([^;]+);", content)
                    locations = cls._extract_locations(content)

                    domains.append(
                        {
                            "domain": domain_match.group(1).strip()
                            if domain_match
                            else "N/A",
                            "filename": filename,
                            "paths": [
                                {"path": loc["path"], "port": loc["port"]}
                                for loc in locations
                            ],
                        }
                    )
                except Exception:
                    continue

        domains.sort(key=lambda x: x["domain"])
        return domains

    # ---------- write (existing domain, no certbot) ----------

    @classmethod
    def _write_config(cls, domain: str, content: str):
        script_path = os.path.join(cls.SCRIPT_DIR, "write_nginx_config.sh")
        process = subprocess.Popen(
            ["sudo", "bash", script_path, domain],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = process.communicate(input=content)
        return process.returncode == 0, stdout + stderr

    @classmethod
    def add_path(cls, domain: str, path: str, port: str):
        if not cls.is_valid_domain(domain):
            return False, "유효하지 않은 도메인입니다."

        norm_path = cls.normalize_path(path)
        if norm_path is None:
            return False, "유효하지 않은 경로입니다."

        if not (port.isdigit() and 1 <= int(port) <= 65535):
            return False, "유효하지 않은 포트입니다."

        config_path = os.path.join(cls.SITES_AVAILABLE, domain)
        if not os.path.exists(config_path):
            return (
                False,
                "해당 도메인이 존재하지 않습니다. '새 도메인 추가'로 먼저 생성하세요.",
            )

        with open(config_path, "r") as f:
            content = f.read()

        locations = cls._extract_locations(content)
        if any(loc["path"] == norm_path for loc in locations):
            return False, "이미 존재하는 경로입니다."

        block = cls._build_location_block(norm_path, port)
        if locations:
            insert_at = locations[-1]["end"]
            new_content = content[:insert_at] + "\n" + block + content[insert_at:]
        else:
            name_match = re.search(r"server_name\s+[^;]+;", content)
            if not name_match:
                return False, "설정 파일 형식을 인식할 수 없습니다."
            insert_at = name_match.end()
            new_content = content[:insert_at] + "\n\n" + block + content[insert_at:]

        return cls._write_config(domain, new_content)

    @classmethod
    def edit_path_port(cls, domain: str, path: str, port: str):
        if not cls.is_valid_domain(domain):
            return False, "유효하지 않은 도메인입니다."

        norm_path = cls.normalize_path(path)
        if norm_path is None:
            return False, "유효하지 않은 경로입니다."

        if not (port.isdigit() and 1 <= int(port) <= 65535):
            return False, "유효하지 않은 포트입니다."

        config_path = os.path.join(cls.SITES_AVAILABLE, domain)
        if not os.path.exists(config_path):
            return False, "해당 도메인이 존재하지 않습니다."

        with open(config_path, "r") as f:
            content = f.read()

        locations = cls._extract_locations(content)
        target = next((loc for loc in locations if loc["path"] == norm_path), None)
        if target is None:
            return False, "해당 경로를 찾을 수 없습니다."

        block = content[target["start"] : target["end"]]
        new_block, n = re.subn(
            r"(proxy_pass\s+http://localhost:)\d+", rf"\g<1>{port}", block, count=1
        )
        if n == 0:
            return False, "포트 설정을 찾을 수 없습니다."

        new_content = content[: target["start"]] + new_block + content[target["end"] :]
        return cls._write_config(domain, new_content)

    @classmethod
    def delete_path(cls, domain: str, path: str):
        if not cls.is_valid_domain(domain):
            return False, "유효하지 않은 도메인입니다.", False

        norm_path = cls.normalize_path(path)
        if norm_path is None:
            return False, "유효하지 않은 경로입니다.", False

        config_path = os.path.join(cls.SITES_AVAILABLE, domain)
        if not os.path.exists(config_path):
            return False, "해당 도메인이 존재하지 않습니다.", False

        with open(config_path, "r") as f:
            content = f.read()

        locations = cls._extract_locations(content)
        target = next((loc for loc in locations if loc["path"] == norm_path), None)
        if target is None:
            return False, "해당 경로를 찾을 수 없습니다.", False

        if len(locations) <= 1:
            return False, "마지막 경로입니다. 도메인 전체 삭제가 필요합니다.", True

        start, end = target["start"], target["end"]
        # 블록 앞의 들여쓰기/개행도 함께 제거
        while start > 0 and content[start - 1] in " \t":
            start -= 1
        if start > 0 and content[start - 1] == "\n":
            start -= 1
        new_content = content[:start] + content[end:]

        ok, msg = cls._write_config(domain, new_content)
        return ok, msg, False

    # ---------- new domain creation (certbot) ----------

    @classmethod
    def add_domain(cls, domain: str, email: str, port: str, path: str = "/"):
        script_path = os.path.join(cls.SCRIPT_DIR, "add_nginx.sh")
        inputs = f"{domain}\n{email}\n{port}\n{path}\n"
        process = subprocess.Popen(
            ["sudo", "bash", script_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = process.communicate(input=inputs)
        return process.returncode == 0, stdout + stderr

    @classmethod
    def delete_domain(cls, domain_name: str):
        try:
            # 1. Certbot 인증서 삭제
            subprocess.run(
                [
                    "sudo",
                    "certbot",
                    "delete",
                    "--cert-name",
                    domain_name,
                    "--non-interactive",
                ],
                check=False,
            )
            # 2. Nginx 설정 파일 삭제
            subprocess.run(
                ["sudo", "rm", f"/etc/nginx/sites-enabled/{domain_name}"], check=False
            )
            subprocess.run(
                ["sudo", "rm", f"/etc/nginx/sites-available/{domain_name}"], check=False
            )
            # 3. Nginx Reload
            subprocess.run(["sudo", "nginx", "-t"], check=True)
            subprocess.run(["sudo", "systemctl", "reload", "nginx"], check=True)
            return True, "Success"
        except Exception as e:
            return False, str(e)
