import json
import os
from functools import lru_cache

from dotenv import load_dotenv

# import 시점에 MODE를 확정하므로, 호출부가 load_dotenv()를 부르기 전에 이 모듈을
# import해도 .env의 MODE가 반영되도록 여기서 직접 읽어둔다.
load_dotenv()

MODE = int(os.getenv("MODE", 1))
IS_DEV = MODE == 0

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVICES_FILE = os.path.join(REPO_ROOT, "services.json")


@lru_cache(maxsize=1)
def _config() -> dict:
    with open(SERVICES_FILE, encoding="utf-8") as f:
        return json.load(f)


def _service(name: str) -> dict:
    try:
        return _config()["services"][name]
    except KeyError:
        known = ", ".join(sorted(_config()["services"]))
        raise KeyError(f"services.json에 '{name}' 서비스가 없다. 사용 가능: {known}")


def service_names() -> list[str]:
    return sorted(_config()["services"])


def port(name: str) -> int:
    svc = _service(name)
    value = svc["dev_port"] if IS_DEV else svc["prod_port"]
    if value is None:
        # dev가 없는 서비스는 dev로 켜도 운영 쪽을 그대로 본다.
        value = svc["prod_port"]
    if value is None:
        raise ValueError(f"'{name}'에는 포트가 정의돼 있지 않다 (services.json)")
    return value


def domain(name: str) -> str:
    svc = _service(name)
    return (svc["dev_domain"] if IS_DEV else svc["prod_domain"]) or svc["prod_domain"]


def internal_url(name: str) -> str:
    return f"http://localhost:{port(name)}"


def internal_api(name: str) -> str:
    return f"{internal_url(name)}/api"


def public_url(name: str) -> str:
    return f"https://{domain(name)}{_service(name).get('public_path', '')}"


def public_ws_url(name: str) -> str:
    return f"wss://{domain(name)}{_service(name).get('public_path', '')}"


def all_domains(name: str) -> list[str]:
    svc = _service(name)
    return [d for d in (svc["prod_domain"], svc["dev_domain"]) if d]


def all_origins(name: str) -> list[str]:
    return [f"https://{d}" for d in all_domains(name)]


# ── 전역 값 ────────────────────────────────────────────────────────────────
COOKIE_DOMAIN = _config()["cookie_domain"]
WEBAUTHN_RP_ID = _config()["webauthn_rp_id"]

# 중앙 로그인은 dev/prod가 계정을 공유하므로 항상 운영 홈페이지가 담당한다
# (services.json의 login_service / _login_comment 참고).
_LOGIN_SVC = _config()["login_service"]
LOGIN_ORIGIN = f"https://{_service(_LOGIN_SVC)['prod_domain']}"
LOGIN_URL = f"{LOGIN_ORIGIN}/login"

# 이 인스턴스 자신이 서빙되는 주소 — 인증 메일 링크처럼 "지금 이 인스턴스"를
# 가리켜야 하는 곳에 쓴다.
HOMEPAGE_URL = public_url("homepage")
