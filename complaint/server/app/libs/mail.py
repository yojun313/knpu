import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv

load_dotenv()

def sendEmail(receiver, title, text, attachment_path=None):
    sender = "knpubigmac2024@gmail.com"
    MailPassword = os.getenv("MAIL_PASSWORD")

    msg = MIMEMultipart()
    msg['Subject'] = title
    msg['From'] = sender
    msg['To'] = receiver

    msg.attach(MIMEText(text, 'plain'))

    if attachment_path and os.path.exists(attachment_path):
        try:
            with open(attachment_path, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
            
            encoders.encode_base64(part)
            
            filename = os.path.basename(attachment_path)

            part.add_header(
                "Content-Disposition",
                "attachment",
                filename=filename 
            )
            
            msg.attach(part)
        except Exception as e:
            print(f"파일 첨부 중 오류 발생: {e}")

    smtp_server = "smtp.gmail.com"
    smtp_port = 587

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(sender, MailPassword)
        server.sendmail(sender, receiver, msg.as_string())