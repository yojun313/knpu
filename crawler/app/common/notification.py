import os
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import os
from dotenv import load_dotenv
import requests

from db import discord_notifications_db, get_userinfo

load_dotenv()

sender = os.getenv("MAIL_SENDER")
MailPassword = os.getenv("MAIL_PASSWORD")


def sendMail(receiver, title, text):
    msg = MIMEMultipart()
    msg["Subject"] = title
    msg["From"] = sender
    msg["To"] = receiver

    msg.attach(MIMEText(text, "plain"))

    smtp_server = "smtp.gmail.com"
    smtp_port = 587

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(sender, MailPassword)
        server.sendmail(sender, receiver, msg.as_string())


def sendDiscord(msg, channel_key, requester=None):
    try:
        content = f"👤 **{requester}**\n{msg}" if requester else msg
        discord_notifications_db.insert_one(
            {
                "channel_key": channel_key,
                "content": content,
                "embed": None,
                "actions": None,
                "status": "pending",
                "created_at": datetime.now(timezone.utc),
                "sent_at": None,
                "error": None,
            }
        )
    except Exception:
        pass


def sendDiscordDM(user_ids, msg, requester=None):
    try:
        ids = sorted({uid for uid in (user_ids or []) if uid})
        if not ids:
            return
        content = f"👤 **{requester}**\n{msg}" if requester else msg
        discord_notifications_db.insert_one(
            {
                "channel_key": None,
                "dm_user_ids": ids,
                "content": content,
                "embed": None,
                "actions": None,
                "status": "pending",
                "created_at": datetime.now(timezone.utc),
                "sent_at": None,
                "error": None,
            }
        )
    except Exception:
        pass


def notifyRequester(requester, email, title, text):
    """요청자 본인에게 보내는 크롤링 상태 알림.

    디스코드 인증(discord_id 연동)이 되어있으면 디스코드 DM을 우선 시도하고,
    봇이 실제로 DM 전송에 실패한 경우에만(사용자가 서버를 나갔거나 DM을 막아둔 경우 등)
    봇이 이메일로 폴백해서 보낸다(bot/cogs/cog_notifications.py의 _send_dm 참고).
    아예 디스코드 인증이 안 된 사용자는 여기서 바로 이메일로 보낸다."""
    info = get_userinfo(requester) if requester else None
    discord_id = info.get("discord_id") if info else None

    if not discord_id:
        sendMail(email, title, text)
        return

    try:
        discord_notifications_db.insert_one(
            {
                "channel_key": None,
                "dm_user_ids": [discord_id],
                "content": f"{title}\n{text}",
                "fallback_email": email,
                "fallback_subject": title,
                "fallback_text": text,
                "embed": None,
                "actions": None,
                "status": "pending",
                "created_at": datetime.now(timezone.utc),
                "sent_at": None,
                "error": None,
            }
        )
    except Exception:
        # 큐 등록 자체가 실패하면(예: DB 장애) 폴백 판단을 봇에 맡길 수 없으므로
        # 여기서 바로 이메일로 보낸다.
        sendMail(email, title, text)
