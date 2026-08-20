from datetime import datetime, timezone

from system.db import discord_notifications_db


def notify_discord(
    channel_key: str,
    content: str,
    embed: dict | None = None,
    actions: dict | None = None,
) -> None:
    try:
        discord_notifications_db.insert_one(
            {
                "channel_key": channel_key,
                "content": content,
                "embed": embed,
                "actions": actions,
                "status": "pending",
                "created_at": datetime.now(timezone.utc),
                "sent_at": None,
                "error": None,
            }
        )
    except Exception:
        # 알림 발행 실패가 본 기능(버전 등록/버그 신고/분석 오류 등)을 막으면 안 된다.
        pass
