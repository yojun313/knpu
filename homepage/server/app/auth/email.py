import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def sendEmail(receiver: str, title: str, text: str):
    sender = os.getenv("MAIL_SENDER")
    mail_password = os.getenv("MAIL_PASSWORD")

    msg = MIMEMultipart()
    msg["Subject"] = title
    msg["From"] = sender
    msg["To"] = receiver

    msg.attach(MIMEText(text, "plain"))

    smtp_server = "smtp.gmail.com"
    smtp_port = 587

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(sender, mail_password)
        server.sendmail(sender, receiver, msg.as_string())
