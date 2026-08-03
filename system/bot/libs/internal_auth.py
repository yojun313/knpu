import os
import datetime

import jwt

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")


def mint_admin_token() -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": "discord-bot",
        "name": "Discord Bot",
        "role": "admin",
        "exp": now + datetime.timedelta(minutes=5),
        "iat": now,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
