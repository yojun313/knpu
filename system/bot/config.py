import os
import sys

from dotenv import load_dotenv

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# MODE는 pm2 env로 들어오지만, pm2 밖에서 띄울 때를 위해 .env를 먼저 읽고 나서
# system.endpoints(=import 시점에 MODE를 확정한다)를 가져온다.
load_dotenv()

from system.endpoints import internal_api, public_url  # noqa: E402

# LLM 프록시(/api/llm/*)는 manager/server가 들고 있다 — 예전엔 홈페이지 포트(8000)로
# 잘못 향해 있어서 404가 났다.
LLM_API_URL = internal_api("manager")
LLM_KEY = os.getenv("ADMIN_TOKEN")

# 가입 승인/거절(/api/auth/admin/requests/*)은 홈페이지가 들고 있다 — 예전엔 크롤러
# 포트(8002)로 잘못 향해 있었다.
HOMEPAGE_API_URL = internal_api("homepage")

# 디스코드 인증 링크는 사용자 브라우저에서 직접 여는 것이므로 localhost가 아니라
# 공개 도메인이어야 한다 (HOMEPAGE_API_URL은 봇↔서버 내부 통신용이라 다르다).
HOMEPAGE_WEB_URL = public_url("homepage")

# 인증 관련 값도 CHANNEL_IDS와 같은 이유로 슬래시 명령어로 바꾸는 기능을 두지 않고
# 코드에 고정한다 (/인증설정, /인증전역할, /인증로그채널, /시작하기 명령어 폐지).
VERIFY_GUILD_ID = 1491262818865905674
VERIFY_ROLE_ID = 1491263198286839950  # 인증 완료 시 부여할 일반 유저 역할
VERIFY_UNVERIFIED_ROLE_ID = 1491269986017083532  # 인증 전 역할
VERIFY_LOG_CHANNEL_ID = 1499368692583239821  # 인증 로그 채널
VERIFY_CHANNEL_ID = 1491269750603518092  # Verify 버튼 임베드가 있는 채널

# 채널 지정을 슬래시 명령어로 관리자가 나중에 설정하게 두면 설정을 깜빡했을 때
# 알림이 조용히 유실된다(실제로 업데이트 로그 채널이 이 문제로 미설정 상태였다).
# 그래서 채널은 여기 코드에 고정해두고, 슬래시 명령어로 바꾸는 기능은 두지 않는다.
CHANNEL_IDS = {
    "manager_update": 1508435006547034204,  # MANAGER┃update-Log — 새 버전 배포 (전체 공개)
    "system_error": 1499376613186469940,  # SYSTEM┃Error-Log — knpu/ 전체 서비스의 크래시/버그 리포트 (관리자 전용)
    "announcements": 1491270408958116024,  # 📢┃공지사항 — 자유게시판 공지 브로드캐스트 (전체 공개)
    "crawler_status": 1531245548927975454,  # 크롤러-상태-알림 — 크롤링 완료/중단 (전체 공개). 기존 채널이 삭제되어 재생성함(2026-07-27)
    "crawler_error": 1531245550962217010,  # 크롤러-오류-로그 — 크롤링 오류 (관리자 전용). 기존 채널이 삭제되어 재생성함(2026-07-27)
    "admin_ops": 1530893674265710664,  # 🔔┃운영-알림 — 빌드 완료, 사용자 앱 업데이트 등 (관리자 전용)
    "signup_approval": 1530893676010537093,  # 📝┃가입-승인-요청 — 홈페이지 회원가입 승인 대기 (관리자 전용)
}
