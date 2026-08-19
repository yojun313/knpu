"""서비스 간 호출 주소를 MODE 한 곳에서 계산한다.

MODE=0(dev)과 MODE=1(prod)은 DB/계정을 전부 공유하고(system/db/__init__.py 참고),
갈리는 것은 **접속 포트와 공개 URL뿐**이다. 규칙은 하나다 — dev 포트 = prod 포트 + 10000,
dev 도메인 = "dev-" + prod 서브도메인.

예전에는 이 규칙이 서비스마다 손으로 복사돼 있었고, 그 과정에서 포트를 잘못 적은
곳들이 있었다(봇이 홈페이지 API를 크롤러 포트로, GPU 워커가 매니저 알림을 홈페이지
포트로 호출하는 등). 새로 서비스 간 호출을 추가할 때는 여기 상수를 쓴다.
"""

import os

from dotenv import load_dotenv

# import 시점에 MODE를 확정하므로, 호출부가 load_dotenv()를 부르기 전에 이 모듈을
# import해도 .env의 MODE가 반영되도록 여기서 직접 읽어둔다.
load_dotenv()

MODE = int(os.getenv("MODE", 1))
IS_DEV = MODE == 0

# prod 기준 포트. dev는 여기에 +10000 한 포트를 쓴다.
_PORTS = {
    "homepage": 8000,
    "manager": 8001,
    "crawler": 8002,
    "network": 8003,
    "statistics": 8004,
    "progress": 8006,  # manager/web — 진행상황 서버
    "ahp": 8007,
    "kemkim": 8008,
    "dashboard": 8009,
    "complaint": 8010,
}

# 공개 도메인의 서브도메인. homepage만 서브도메인이 없어 dev에서 "dev.knpu.re.kr"가 된다.
_SUBDOMAINS = {
    "homepage": "",
    "manager": "manager",
    "crawler": "crawler",
    "network": "network",
    "statistics": "statistics",
    "progress": "manager",  # 진행상황은 manager 도메인의 /progress 로 노출된다
    "ahp": "ahp",
    "kemkim": "kemkim",
    "dashboard": "dashboard",
    "complaint": "complaint",
}


def port(service: str) -> int:
    """같은 호스트 안에서 그 서비스가 듣고 있는 포트."""
    return _PORTS[service] + (10000 if IS_DEV else 0)


def internal_url(service: str) -> str:
    """서버 간 호출용 주소. 같은 장비에 있으므로 nginx/TLS를 거치지 않는다."""
    return f"http://localhost:{port(service)}"


def internal_api(service: str) -> str:
    return f"{internal_url(service)}/api"


def public_url(service: str) -> str:
    """사용자 브라우저가 여는 주소."""
    sub = _SUBDOMAINS[service]
    if IS_DEV:
        host = f"dev-{sub}.knpu.re.kr" if sub else "dev.knpu.re.kr"
    else:
        host = f"{sub}.knpu.re.kr" if sub else "knpu.re.kr"
    return f"https://{host}"


# 중앙 로그인은 dev/prod가 계정을 공유하므로 항상 운영 홈페이지가 담당한다.
# dev 홈페이지가 내려가 있어도 dev-* 서비스에 로그인할 수 있어야 하기 때문이다
# (system/ui/theme.js가 서비스 링크만 dev로 바꾸고 로그인/홈은 두는 것과 같은 이유).
LOGIN_URL = "https://knpu.re.kr/login"
