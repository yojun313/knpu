import os

import requests

from system.endpoints import internal_api

MANAGER_SERVER_INTERNAL_API = os.getenv(
    "MANAGER_SERVER_INTERNAL_API", internal_api("manager")
)


def notify_discord(channel_key: str, content: str) -> None:
    try:
        kind = "error" if channel_key == "system_error" else "ops"
        requests.post(
            f"{MANAGER_SERVER_INTERNAL_API}/users/admin/notify",
            json={"message": content, "kind": kind},
            timeout=5,
        )
    except Exception:
        pass
