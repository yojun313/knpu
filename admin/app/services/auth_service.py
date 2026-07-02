import random
import string
from datetime import datetime, timedelta
from app.db import users_col, manager_db
from app.libs.email import sendEmail

auth_col = manager_db["auth"]


def generate_code():
    return "".join(random.choices(string.digits, k=6))


def request_login(name: str):
    user = users_col.find_one({"name": name, "role": "admin"}, {"_id": 0})
    if not user:
        return None

    code = generate_code()
    auth_col.update_one(
        {"name": name, "type": "code"},
        {
            "$set": {
                "code": code,
                "email": user["email"],
                "expired_at": datetime.now() + timedelta(minutes=5),
            }
        },
        upsert=True,
    )

    sendEmail(
        user["email"],
        "[FPEI] Dashboard Verification Code",
        f"Your verification code is: {code}",
    )
    return user["email"]


def verify_login(name: str, code: str):
    record = auth_col.find_one({"name": name, "code": code, "type": "code"}, {"_id": 0})
    if not record:
        return False

    if datetime.now() > record["expired_at"]:
        return False

    session_id = "".join(random.choices(string.ascii_letters + string.digits, k=32))

    auth_col.insert_one(
        {
            "type": "session",
            "session_id": session_id,
            "name": name,
            "created_at": datetime.now(),
        }
    )

    auth_col.delete_one({"name": name, "type": "code"})

    return session_id


def check_session(session_id: str):
    if not session_id:
        return None

    session = auth_col.find_one(
        {"session_id": session_id, "type": "session"}, {"_id": 0}
    )
    if not session:
        return None

    if datetime.now() > session["created_at"] + timedelta(days=30):
        auth_col.delete_one({"session_id": session_id, "type": "session"})
        return None

    return session["name"]
