# -*- coding: utf-8 -*-
import sys
import json
from openai import OpenAI
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials
import os
import pickle
import io
from docx2pdf import convert


pdf_folder_path = "C:/Users/qwe/Desktop/VSCODE/GPT WEB/pdf_storage/"
pdf_statement_folder_path = "C:/Users/qwe/Desktop/VSCODE/GPT WEB/pdf_statement_storage/"
storage_json = 'C:/Users/qwe/Desktop/VSCODE/GPT WEB/public/storage.json'
SCOPES = ['https://www.googleapis.com/auth/drive']

# 인증 파일 경로
creds = None
if os.path.exists('token.pickle'):
    with open('token.pickle', 'rb') as token:
        creds = pickle.load(token)

# 인증 정보가 없거나 유효하지 않으면 새로운 인증을 수행
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request()) # 유효기간이 만료된 토큰 새로고침
    else:
        # 인증 정보 파일 public/storage.json에서 인증을 진행
        flow = InstalledAppFlow.from_client_secrets_file(
            storage_json, SCOPES)
        # access_type='offline' 추가
        creds = flow.run_local_server(port=0, access_type='offline')
    # 새롭게 받은 인증 정보를 'token.pickle'에 저장
    with open('token.pickle', 'wb') as token:
        pickle.dump(creds, token)

# Google Drive API 서비스 구축
service = build('drive', 'v3', credentials=creds)


def upload_folder(drive_service, folder_path, parent_folder_id=None):
    folder_name = os.path.basename(folder_path)
    
    # 폴더 생성
    file_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
scss
Copy code
}
if parent_folder_id:
    file_metadata['parents'] = [parent_folder_id]
folder = drive_service.files().create(body=file_metadata, fields='id').execute()
folder_id = folder.get('id')

# 폴더 내의 파일 업로드
for file_name in os.listdir(folder_path):
    file_path = os.path.join(folder_path, file_name)
    if os.path.isfile(file_path):
        file_metadata = {'name': file_name, 'parents': [folder_id]}
        media = MediaFileUpload(file_path, resumable=True)
        file = drive_service.files().create(body=file_metadata, media_body=media,