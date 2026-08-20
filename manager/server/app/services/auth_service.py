import os
import jwt


def get_uid_from_bearer(authorization: str | None) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[len("Bearer ") :]
    try:
        payload = jwt.decode(
            token, os.getenv("JWT_SECRET"), algorithms=[os.getenv("JWT_ALGORITHM")]
        )
        return payload.get("sub")
    except jwt.InvalidTokenError:
        return None
