from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
from dotenv import load_dotenv
import os

load_dotenv()

def sendEmail(receiver, title, text):
    sender = "knpubigmac2024@gmail.com"
    MailPassword = os.getenv('MAIL_PASSWORD')

    msg = MIMEMultipart()
    msg['Subject'] = title
    msg['From'] = sender
    msg['To'] = receiver

    msg.attach(MIMEText(text, 'plain'))

    smtp_server = "smtp.gmail.com"
    smtp_port = 587

    # SMTP 연결 및 메일 보내기
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(sender, MailPassword)
        server.sendmail(sender, receiver, msg.as_string())