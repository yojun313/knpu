import random
import string
from datetime import datetime, timedelta
from app.db import users_col, manager_db
from app.libs.email import sendEmail

auth_codes_col = manager_db["auth-codes"]
sessions_col = manager_db["sessions"]

def generate_code():
    return ''.join(random.choices(string.digits, k=6))

def request_login(name: str):
    user = users_col.find_one({"name": name, "role": "admin"})
    if not user:
        return None
    
    code = generate_code()
    auth_codes_col.update_one(
        {"name": name},
        {"$set": {"code": code, "email": user["email"], "expired_at": datetime.now() + timedelta(minutes=5)}},
        upsert=True
    )
    
    sendEmail(user["email"], "[PAILAB] Dashboard Verification Code", f"Your verification code is: {code}")
    return user["email"]

def verify_login(name: str, code: str):
    record = auth_codes_col.find_one({"name": name, "code": code})
    if not record:
        return False
    
    if datetime.now() > record["expired_at"]:
        return False
        
    session_id = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    sessions_col.insert_one({
        "session_id": session_id,
        "name": name,
        "created_at": datetime.now()
    })
    
    auth_codes_col.delete_one({"name": name})
    return session_id

def check_session(session_id: str):
    if not session_id:
        return False
    session = sessions_col.find_one({"session_id": session_id})
    return session["name"] if session else None