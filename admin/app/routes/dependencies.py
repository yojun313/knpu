from fastapi import Request, HTTPException
from app.services.auth_service import check_session

async def get_current_user(request: Request):
    session_id = request.cookies.get("session_id")
    user_name = check_session(session_id)
    if not user_name:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return user_name