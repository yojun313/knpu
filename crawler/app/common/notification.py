import os
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import os
from dotenv import load_dotenv
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

    with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
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


def _post_crawler_status(header: str, email: str, title: str, text: str, linked: bool):
    try:
        discord_notifications_db.insert_one(
            {
                "channel_key": "crawler_status",
                "content": f"{header}\n{title}\n{text}",
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
        linked = False

    if not linked:
        try:
            sendMail(email, title, text)
        except Exception:
            pass


def notifyRequester(requester, email, title, text):
    info = get_userinfo(requester) if requester else None
    discord_id = info.get("discord_id") if info else None

    header = f"<@{discord_id}>" if discord_id else f"👤 **{requester or '알 수 없음'}**"
    _post_crawler_status(header, email, title, text, linked=bool(discord_id))


def notifyRequesterAndAdmins(requester, email, title, text, admin_discord_ids):
    info = get_userinfo(requester) if requester else None
    discord_id = info.get("discord_id") if info else None

    admin_mentions = " ".join(
        f"<@{uid}>"
        for uid in sorted(set(admin_discord_ids or []) - {discord_id})
        if uid
    )
    requester_part = (
        f"<@{discord_id}>" if discord_id else f"👤 **{requester or '알 수 없음'}**"
    )
    header = f"{admin_mentions} {requester_part}".strip()

    _post_crawler_status(header, email, title, text, linked=bool(discord_id))
