from fastapi import Request, HTTPException, Depends
from fastapi.responses import RedirectResponse
from app.services.auth_service import check_session


async def get_current_user(request: Request):
    session_id = request.cookies.get("session_id")
    user_name = check_session(session_id)

    if not user_name:
        raise HTTPException(status_code=307, detail="Not logged in")

    return user_name
