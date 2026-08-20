import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib
from dotenv import load_dotenv

load_dotenv()

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587


def _build_message(sender: str, receiver: str, title: str, text: str) -> MIMEMultipart:
    msg = MIMEMultipart()
    msg["Subject"] = title
    msg["From"] = sender
    msg["To"] = receiver
    msg.attach(MIMEText(text, "plain"))
    return msg


def sendEmail(receiver: str, title: str, text: str) -> None:
    sender = os.getenv("MAIL_SENDER")
    mail_password = os.getenv("MAIL_PASSWORD")
    msg = _build_message(sender, receiver, title, text)

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(sender, mail_password)
        server.sendmail(sender, receiver, msg.as_string())


async def sendEmailAsync(receiver: str, title: str, text: str) -> None:
    sender = os.getenv("MAIL_SENDER")
    mail_password = os.getenv("MAIL_PASSWORD")
    msg = _build_message(sender, receiver, title, text)

    await aiosmtplib.send(
        msg,
        hostname=SMTP_SERVER,
        port=SMTP_PORT,
        username=sender,
        password=mail_password,
        start_tls=True,
    )
