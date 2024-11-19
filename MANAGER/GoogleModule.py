# -*- coding: utf-8 -*-##
import os

CRAWLERPACKAGE_PATH = os.path.dirname(os.path.abspath(__file__))
CRAWLER_PATH        = os.path.dirname(CRAWLERPACKAGE_PATH)

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import os
import pickle
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

class GoogleModule:
    
    def __init__(self):
        # Gmail
        self.sender = "knpubigmac2024@gmail.com"
        self.MailPassword = 'vygn nrmh erpf trji'
        
    def SendMail(self, receiver, title, text):
        
        msg = MIMEMultipart()
        msg['Subject'] = title
        msg['From'] = self.sender
        msg['To'] = receiver

        msg.attach(MIMEText(text, 'plain'))
        
        smtp_server = "smtp.gmail.com"
        smtp_port = 587

        # SMTP 연결 및 메일 보내기
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(self.sender, self.MailPassword)
            server.sendmail(self.sender, receiver, msg.as_string())
