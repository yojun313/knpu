"""메일 발송 유틸. 동기(sendEmail, smtplib)와 비동기(sendEmailAsync, aiosmtplib) 둘 다 제공한다
— 디스코드 봇처럼 이벤트 루프 안에서 호출하는 곳은 비동기판을 쓴다.

homepage(app/auth/email.py)와 complaint(app/libs/mail.py)는 각자 다른 메일 템플릿/첨부파일
요구사항이 있는 별도 구현이라 통합 대상에서 제외했다."""

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
