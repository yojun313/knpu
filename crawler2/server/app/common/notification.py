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
from dotenv import load_dotenv
import requests

load_dotenv()

token_path = os.getenv('DATA_PATH')
storage_json_path = os.path.join(token_path, 'storage.json')

# Gmail
sender = "knpubigmac2024@gmail.com"
MailPassword = os.getenv('MAIL_PASSWORD')
SCOPES = ['https://www.googleapis.com/auth/drive']
creds = None

if os.path.exists(token_path + '/' + 'token.pickle'):
    with open(token_path + '/' + 'token.pickle', 'rb') as token:
        creds = pickle.load(token)

if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request()) # 유효기간이 만료된 토큰 새로고침
    """else:
        # 인증 정보 파일 public/storage.json에서 인증을 진행
        flow = InstalledAppFlow.from_client_secrets_file(
            storage_json_path, SCOPES)
        # access_type='offline' 추가
        creds = flow.run_local_server(port=0, access_type='offline')
    # 새롭게 받은 인증 정보를 'token.pickle'에 저장
    with open(token_path + '/' + 'token.pickle', 'wb') as token:
        pickle.dump(creds, token)
        

drive_service = build('drive', 'v3', credentials=creds)
"""
def sendMail(receiver, title, text):
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


'''
object = GooglePackage('/Users/yojunsmacbookprp/Documents/BIGMACLAB/CRAWLER_ASYNC')
path = object.UploadFolder('/Users/yojunsmacbookprp/Documents/BIGMACLAB/CRAWLER_ASYNC/scrapdata/Naver_News_무고죄_20230101_20230101_0716_2008')
print(path)
object.sendMail('moonyojun@naver.com', 'test', 'path')
'''

def sendPushOver(msg, user_key):
    app_key_list  = ["a273soeggkmq1eafdyghexusve42bq", "a39cudwdti3ap97kax9pmvp6gdm2b9"]#env나 db에서 불러오기?
    for app_key in app_key_list:
        try:
            # Pushover API 설정
            url = 'https://api.pushover.net/1/messages.json'
            # 메시지 내용
            message = {
                'token': app_key,
                'user': user_key,
                'message': msg
            }
            # Pushover에 요청을 보냄
            response = requests.post(url, data=message)
            break
        except:
            continue