from fastapi import Request, HTTPException


def get_current_user(request: Request) -> dict:
    user = request.scope.get("state", {}).get("user")
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    return user


def check_owner_or_admin(user: dict, doc: dict):
    if user.get("role") == "admin":
        return
    if user.get("uid") and doc.get("userUid") and user["uid"] == doc["userUid"]:
        return
    raise HTTPException(
        status_code=403, detail="관리자 또는 크롤링 요청자만 가능합니다"
    )
