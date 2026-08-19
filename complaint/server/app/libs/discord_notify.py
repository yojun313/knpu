import os
import requests

MODE = int(os.getenv("MODE", 1))

MANAGER_SERVER_INTERNAL_API = os.getenv(
    "MANAGER_SERVER_INTERNAL_API", f"http://localhost:{18001 if MODE == 0 else 8001}/api"
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
