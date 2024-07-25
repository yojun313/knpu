# -*- coding: utf-8 -*-
import os

CRAWLERPACKAGE_PATH = os.path.dirname(os.path.abspath(__file__))
CRAWLER_PATH        = os.path.dirname(CRAWLERPACKAGE_PATH)
COLLECTION_PATH     = os.path.join(CRAWLER_PATH, 'Collection')

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
    
    def __init__(self, token_path):
        
        # Gmail
        self.sender = "knpubigmac2024@gmail.com"
        self.MailPassword = 'vygn nrmh erpf trji'
        
        # Google Drive
        self.parent_folder_id = "1K3YTj9h_BMjpGyoDQYkWycqmnJLCxPCA"
        self.storage_json_path = os.path.join(COLLECTION_PATH, 'storage.json')
        
        SCOPES = ['https://www.googleapis.com/auth/drive']

        creds = None
        if os.path.exists(token_path + '/' + 'token.pickle'):
            with open(token_path + '/' + 'token.pickle', 'rb') as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request()) # 유효기간이 만료된 토큰 새로고침
            else:
                # 인증 정보 파일 public/storage.json에서 인증을 진행
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.storage_json_path, SCOPES)
                # access_type='offline' 추가
                creds = flow.run_local_server(port=0, access_type='offline')
            # 새롭게 받은 인증 정보를 'token.pickle'에 저장
            with open(token_path + '/' + 'token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        
        self.drive_service = build('drive', 'v3', credentials=creds)
        
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
    
    def UploadFolder(self, folder_path):
        
        folder_name = os.path.basename(folder_path)
            
        file_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
        }
        
        if self.parent_folder_id:
            file_metadata['parents'] = [self.parent_folder_id]
        
        folder = self.drive_service.files().create(body=file_metadata, fields='id').execute()
        folder_id = folder.get('id')
        
        for file_name in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file_name)
            if os.path.isfile(file_path):
                file_metadata = {'name': file_name, 'parents': [folder_id]}
                media = MediaFileUpload(file_path, resumable=True)
                file = self.drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        
        drive_folder_link = f"https://drive.google.com/drive/folders/{folder_id}"
        return drive_folder_link
'''
object = GooglePackage('/Users/yojunsmacbookprp/Documents/BIGMACLAB/CRAWLER_ASYNC')
path = object.UploadFolder('/Users/yojunsmacbookprp/Documents/BIGMACLAB/CRAWLER_ASYNC/scrapdata/Naver_News_무고죄_20230101_20230101_0716_2008')
print(path)
object.SendMail('moonyojun@naver.com', 'test', 'path')
'''