"""1회용 부트스트랩 스크립트: 승인해줄 관리자가 아직 없는 상태에서 최초 관리자 계정을 만든다.

사용법 (homepage/server 디렉토리에서):
    python scripts/create_admin.py

대화형으로 아이디/이름/이메일/비밀번호를 입력받아 status=approved, role=admin,
email_verified=true 상태의 계정을 homepage.users 컬렉션에 바로 생성한다.
이후 다른 모든 구성원은 이 관리자의 승인을 받아 정식 가입 절차를 밟는다.
"""

import getpass
import sys
import uuid
from datetime import datetime

sys.path.insert(0, ".")

from app.db import users_db
from app.auth.hashing import hash_password


def main():
    print("=== KNPU 최초 관리자 계정 생성 ===")
    username = input("아이디: ").strip()
    if users_db.find_one({"username": username}):
        print(f"이미 존재하는 아이디입니다: {username}")
        return

    name = input("이름: ").strip()
    email = input("이메일: ").strip()
    if users_db.find_one({"email": email}):
        print(f"이미 사용 중인 이메일입니다: {email}")
        return

    password = getpass.getpass("비밀번호 (8자 이상): ")
    if len(password) < 8:
        print("비밀번호는 8자 이상이어야 합니다")
        return
    password_confirm = getpass.getpass("비밀번호 확인: ")
    if password != password_confirm:
        print("비밀번호가 일치하지 않습니다")
        return

    now = datetime.now()
    users_db.insert_one(
        {
            "uid": str(uuid.uuid4()),
            "username": username,
            "name": name,
            "email": email,
            "password_hash": hash_password(password),
            "role": "admin",
            "status": "approved",
            "email_verified": True,
            "created_at": now,
            "approved_at": now,
            "approved_by": "bootstrap",
            "updated_at": now,
        }
    )
    print(
        f"\n관리자 계정 '{username}'이(가) 생성되었습니다. https://knpu.re.kr/login 에서 로그인하세요."
    )


if __name__ == "__main__":
    main()
