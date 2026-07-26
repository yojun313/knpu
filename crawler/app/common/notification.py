import os
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import os
from dotenv import load_dotenv
import requests

from db import discord_notifications_db

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
    """discord.notifications 큐에 넣기만 한다 — 실제 전송은 bot/이 폴링해서 처리한다."""
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
    """공개 채널이 아니라 지정된 유저(요청자/관리자)에게만 DM으로 전송한다."""
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
