import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import os
from dotenv import load_dotenv
import requests

load_dotenv()

crawler_pushover_key = os.getenv("CRAWLER_PUSHOVER")
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


def sendPushOver(msg, user_key):
    url = "https://api.pushover.net/1/messages.json"
    message = {"token": crawler_pushover_key, "user": user_key, "message": msg}
    response = requests.post(url, data=message)
