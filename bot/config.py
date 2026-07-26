"""
0: local
1: production
"""

import os
from dotenv import load_dotenv

load_dotenv()

mode = int(os.getenv("MODE"))

LLM_API_URL = "http://localhost:8000/api"
LLM_KEY = os.getenv("ADMIN_TOKEN")

HOMEPAGE_API_URL = "http://localhost:8002/api"

# 채널 지정을 슬래시 명령어로 관리자가 나중에 설정하게 두면 설정을 깜빡했을 때
# 알림이 조용히 유실된다(실제로 업데이트 로그 채널이 이 문제로 미설정 상태였다).
# 그래서 채널은 여기 코드에 고정해두고, 슬래시 명령어로 바꾸는 기능은 두지 않는다.
CHANNEL_IDS = {
    "manager_update": 1508435006547034204,  # MANAGER┃update-Log — 새 버전 배포 (전체 공개)
    "manager_error": 1499376613186469940,  # MANAGER┃Error-Log — 크래시/버그 리포트 (관리자 전용)
    "announcements": 1491270408958116024,  # 📢┃공지사항 — 자유게시판 공지 브로드캐스트 (전체 공개)
    "crawler_status": 1491265838492160000,  # CRAWLER┃Status-Log — 크롤링 완료/중단 (전체 공개)
    "crawler_error": 1491266034030612501,  # CRAWLER┃Error-Log — 크롤링 오류
    "admin_ops": 1530893674265710664,  # 🔔┃운영-알림 — 빌드 완료, 사용자 앱 업데이트 등 (관리자 전용)
    "signup_approval": 1530893676010537093,  # 📝┃가입-승인-요청 — 홈페이지 회원가입 승인 대기 (관리자 전용)
}
