import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
import os

load_dotenv()

async def sendEmail(receiver, title, text):
    sender = os.getenv('MAIL_SENDER')
    MailPassword = os.getenv('MAIL_PASSWORD')

    msg = MIMEMultipart()
    msg['Subject'] = title
    msg['From'] = sender
    msg['To'] = receiver
    msg.attach(MIMEText(text, 'plain'))

    await aiosmtplib.send(
        msg,
        hostname="smtp.gmail.com",
        port=587,
        username=sender,
        password=MailPassword,
        start_tls=True
    )