"""Discord 알림 발행기.

실제 전송은 이 프로세스가 아니라 항상 켜져 있는 디스코드 봇(bot/cogs/cog_notifications.py)이
discord.notifications 컬렉션을 폴링해서 처리한다. 여기서는 큐에 문서 하나 insert하는 것으로
끝나므로, 디스코드 API 장애/레이트리밋이 이 서비스의 요청 처리를 막지 않는다.

channel_key는 bot/config.py의 CHANNEL_IDS에 매핑되어 있어야 실제로 전송된다.
"""

from datetime import datetime, timezone

from app.db import discord_notifications_db


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
        # 알림 발행 실패가 본 기능(버전 등록/버그 신고 등)을 막으면 안 된다.
        pass
