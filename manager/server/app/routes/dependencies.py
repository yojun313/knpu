from fastapi import Request, HTTPException


def get_current_user(request: Request) -> dict:
    user = request.scope.get("state", {}).get("user")
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    return user


def get_uid(request: Request) -> str:
    return get_current_user(request)["uid"]
