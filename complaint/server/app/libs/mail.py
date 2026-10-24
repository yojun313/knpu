import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv

load_dotenv()


def sendEmail(receiver, title, text, attachment=None):
    """attachment: (파일명, bytes). 첨부 내용을 디스크에 쓰지 않고 메모리에서 바로 보낸다."""
    sender = "knpubigmac2024@gmail.com"
    MailPassword = os.getenv("MAIL_PASSWORD")

    msg = MIMEMultipart()
    msg["Subject"] = title
    msg["From"] = sender
    msg["To"] = receiver

    msg.attach(MIMEText(text, "plain"))

    if attachment:
        filename, data = attachment
        part = MIMEBase("application", "octet-stream")
        part.set_payload(data)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(part)

    smtp_server = "smtp.gmail.com"
    smtp_port = 587

    with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
        server.starttls()
        server.login(sender, MailPassword)
        server.sendmail(sender, receiver, msg.as_string())
