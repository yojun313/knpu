# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
import pymysql
import sys
from datetime import date, timedelta
import socket
import datetime
import random
import urllib3
from user_agent import generate_user_agent, generate_navigator
import os
import requests
import json
import random
import pandas as pd
import platform
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service  
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials
import pickle
import io

#pip install lxml

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class Crawler:
    
############################################### 공통 메서드 ###############################################
    
    def __init__(self):
        
        ##################################### 시스템 입력부  #####################################
        
        #연구실 3번 컴퓨터
        if socket.gethostname() == "DESKTOP-HQK7QRT":
            self.filedirectory = "C:/Users/qwe/Desktop/VSCODE/CRAWLER/scrapdata"
            self.proxydirectory = "C:/Users/qwe/Desktop/VSCODE/CRAWLER"
            self.DBpassword = "1234"
            self.proxy_option = "y"
            self.sender = "knpubigmac2024@gmail.com"
            self.MailPassword = 'vygn nrmh erpf trji'
            self.mysql_option = "N" # 켜려면 Y
            self.crawlcom = "3번 컴퓨터"
        
        #연구실 2번 컴퓨터
        elif socket.gethostname() == "DESKTOP-K8PL3FJ":
            self.filedirectory = "C:/Users/skroh/OneDrive/Desktop/VSCODE/CRAWLER/scrapdata"
            self.proxydirectory = "C:/Users/skroh/OneDrive/Desktop/VSCODE/CRAWLER"
            self.DBpassword = "1234"
            self.proxy_option = "y"
            self.sender = "knpubigmac2024@gmail.com"
            self.MailPassword = 'vygn nrmh erpf trji'
            self.mysql_option = "N" # 켜려면 Y
            self.crawlcom = "2번 컴퓨터"
        
        #연구실 1번 컴퓨터
        elif socket.gethostname() == "DESKTOP-UK7NR95":
            self.filedirectory = "C:/Users/Roh/Desktop/VSCODE/CRAWLER/scrapdata"
            self.proxydirectory = "C:/Users/Roh/Desktop/VSCODE/CRAWLER"
            self.DBpassword = "1234"
            self.proxy_option = "y"
            self.sender = "knpubigmac2024@gmail.com"
            self.MailPassword = 'vygn nrmh erpf trji'
            self.mysql_option = "N" # 켜려면 Y
            self.crawlcom = "1번 컴퓨터"
        
        # Yojun's MacBook Pro MACOS
        elif socket.gethostname() == "Yojuns-MacBook-Pro.local":
            self.filedirectory = "/Users/yojunsmacbookprp/Documents/scrapdata"
            self.proxydirectory = "/Users/yojunsmacbookprp/Documents/scrapdata"
            self.DBpassword = "kingsman"
            self.proxy_option = "y"
            self.sender = "knpubigmac2024@gmail.com"
            self.MailPassword = 'vygn nrmh erpf trji'
            self.mysql_option = "N" # 켜려면 Y
            self.crawlcom = "Yojun's MacBook Pro MACOS"
        
        # Yojun's MacBook Pro WINDOW
        elif socket.gethostname() == "YOJUNMACBOOKPRO":
            self.filedirectory = "C:/Users/yojunsmacbookprp/Documents/scrapdata" 
            self.proxydirectory = "C:/Users/yojunsmacbookprp/Documents/scrapdata"
            self.DBpassword = "kingsman"
            self.proxy_option = "y"
            self.sender = "knpubigmac2024@gmail.com"
            self.MailPassword = 'vygn nrmh erpf trji'
            self.mysql_option = "N" # 켜려면 Y
            self.crawlcom = "Yojun's MacBook Pro Window"
        
        # HP OMEN 
        elif socket.gethostname() == "DESKTOP-502IMU5":
            self.filedirectory = "C:/Users/User/Desktop/BIGMACLAB/CRAWLER/scrapdata" 
            self.proxydirectory = "C:/Users/User/Documents/GitHub/BIGMACLAB/CRAWLER"
            self.DBpassword = "kingsman"
            self.proxy_option = "y"
            self.sender = "knpubigmac2024@gmail.com"
            self.MailPassword = 'vygn nrmh erpf trji'
            self.mysql_option = "N" # 켜려면 Y
            self.crawlcom = "HP OMEN"
        
        # HP Z8
        elif socket.gethostname() == "DESKTOP-0I9OM9K":
            self.filedirectory = "C:/Users/User/Desktop/BIGMACLAB/CRAWLER/scrapdata" 
            self.proxydirectory = "C:/Users/User/Documents/GitHub/BIGMACLAB/CRAWLER"
            self.DBpassword = "kingsman"
            self.proxy_option = "y"
            self.sender = "knpubigmac2024@gmail.com"
            self.MailPassword = 'vygn nrmh erpf trji'
            self.mysql_option = "N" # 켜려면 Y
            self.crawlcom = "HP Z8"
            
        self.user_name = input("본인의 이름을 입력하세요: ")
        
        if self.user_name == "이정우":
            self.receiver = "wjddn_1541@naver.com"
        
        elif self.user_name == "문요준":
            self.receiver = "moonyojun@naver.com"
        
        elif self.user_name == "최우철":
            self.receiver = "woc0633@gmail.com"
            
        elif self.user_name == "노승국":
            self.receiver = "science22200@naver.com"
                        
        else:
            print("사용자를 추가하세요(메뉴얼 참고)")
            sys.exit()
            
        #######################################################################################
        
        # proxy.txt 파일에서 프록시 불러옴
        try:
            self.proxy_path = self.proxydirectory+"/proxy.txt"
            self.proxy_list = []
            with open(self.proxy_path) as f:
                lines = f.readlines()
            for ip in lines:
                ip = ip.replace("\n", "")
                self.proxy_list.append(ip)
        except:
            print("프록시 파일이 존재하지 않습니다")
            sys.exit()
            
        # 구글 드라이브 서비스 생성
        
        self.parent_folder_id = "1K3YTj9h_BMjpGyoDQYkWycqmnJLCxPCA"
        self.storage_json = self.proxydirectory+"/storage.json"
        
        SCOPES = ['https://www.googleapis.com/auth/drive']

        creds = None
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request()) # 유효기간이 만료된 토큰 새로고침
            else:
                # 인증 정보 파일 public/storage.json에서 인증을 진행
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.storage_json, SCOPES)
                # access_type='offline' 추가
                creds = flow.run_local_server(port=0, access_type='offline')
            # 새롭게 받은 인증 정보를 'token.pickle'에 저장
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

        self.drive_service = build('drive', 'v3', credentials=creds)
    
        self.starttime = time.time()
        self.now = datetime.datetime.now()
            
        ##################################### 입력부  #####################################
        self.start = input("\nStart Date (ex: 20230101): ") 
        self.end = input("End Date (ex: 20231231): ") 
        self.keyword = input("\nKeyword: ")
        #################################################################################
        
        self.start_dt, self.end_dt = datetime.datetime.strptime(self.start, "%Y%m%d"), datetime.datetime.strptime(self.end, "%Y%m%d")
        self.date_range = (self.end_dt.date() - self.start_dt.date()).days  #분석 날짜 기간
        self.startYear, self.startMonth, self.startDay = int(self.start[0:4]), int(self.start[4:6]), int(self.start[6:8])
        self.endYear, self.endMonth, self.endDay = int(self.end[0:4]), int(self.end[4:6]), int(self.end[6:8])
        self.d_start, self.d_end = datetime.date(self.startYear, self.startMonth, self.startDay), datetime.date(self.endYear, self.endMonth, self.endDay)
        self.deltaD = timedelta(days=1)
        self.currentDate = self.d_start
        
        self.refinedword = self.keyword.split("-")[0].strip().replace('"', "").replace(" ", "")
        
        self.error = False
        self.urlList = []
        
    def upload_folder(self, folder_path):
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
        
        self.drive_folder_link = f"https://drive.google.com/drive/folders/{folder_id}"
        
    def print_status(self, signal, print_type):
        
        self.progress_time = time.time()
        loading_second = self.progress_time - self.starttime
        loadingtime = str(int(loading_second//3600))+"시간 "+str(int(loading_second%3600//60))+"분 "+str(int(loading_second%3600%60))+"초"
        
        if print_type == "news":
            print_type = "기사"
            if signal == -1: # 날짜
                out_str = "\r"+"\033[37m"+"|| 진행: "+"\033[33m"+str(round((self.progress/(self.date_range+1))*100, 1))+"% ("+str(self.progress) + " / " + str(self.date_range+1)+")" + "\033[37m"+" | 경과 시간: "+"\033[33m"+loadingtime + "\033[37m"+" | 날짜: "+"\033[36m"+self.trans_date+ "\033[37m"+" | url 수: "+"\033[33m"+str(len(self.urlList)) + "\033[37m"+" | "+print_type+" 수: "+"\033[33m"+str(len(self.article_list)-1)+"\033[37m"+" | 댓글 수: "+"\033[33m"+str(len(self.reply_list)-1)+"\033[37m"+" | 대댓글 수: "+"\033[33m"+str(len(self.rereply_list)-1) + "\033[37m"+" ||"
                print(out_str, end = "")
            elif signal == 0: # url
                out_str = "\r"+"\033[37m"+"|| 진행: "+"\033[33m"+str(round((self.progress/(self.date_range+1))*100, 1))+"% ("+str(self.progress) + " / " + str(self.date_range+1)+")" + "\033[37m"+" | 경과 시간: "+"\033[33m"+loadingtime + "\033[37m"+" | 날짜: "+"\033[33m"+self.trans_date+ "\033[37m"+" | url 수: "+"\033[36m"+str(len(self.urlList)) + "\033[37m"+" | "+print_type+" 수: "+"\033[33m"+str(len(self.article_list)-1)+"\033[37m"+" | 댓글 수: "+"\033[33m"+str(len(self.reply_list)-1)+"\033[37m"+" | 대댓글 수: "+"\033[33m"+str(len(self.rereply_list)-1) + "\033[37m"+" ||"
                print(out_str, end = "")
            elif signal == 1: # 기사
                out_str = "\r"+"\033[37m"+"|| 진행: "+"\033[33m"+str(round((self.progress/(self.date_range+1))*100, 1))+"% ("+str(self.progress) + " / " + str(self.date_range+1)+")" + "\033[37m"+" | 경과 시간: "+"\033[33m"+loadingtime + "\033[37m"+" | 날짜: "+"\033[33m"+self.trans_date+ "\033[37m"+" | url 수: "+"\033[33m"+str(len(self.urlList)) + "\033[37m"+" | "+print_type+" 수: "+"\033[36m"+str(len(self.article_list)-1)+"\033[37m"+" | 댓글 수: "+"\033[33m"+str(len(self.reply_list)-1)+"\033[37m"+" | 대댓글 수: "+"\033[33m"+str(len(self.rereply_list)-1) + "\033[37m"+" ||"
                print(out_str, end = "")
            elif signal == 2: # 댓글
                out_str = "\r"+"\033[37m"+"|| 진행: "+"\033[33m"+str(round((self.progress/(self.date_range+1))*100, 1))+"% ("+str(self.progress) + " / " + str(self.date_range+1)+")" + "\033[37m"+" | 경과 시간: "+"\033[33m"+loadingtime + "\033[37m"+" | 날짜: "+"\033[33m"+self.trans_date+ "\033[37m"+" | url 수: "+"\033[33m"+str(len(self.urlList)) + "\033[37m"+" | "+print_type+" 수: "+"\033[33m"+str(len(self.article_list)-1)+"\033[37m"+" | 댓글 수: "+"\033[36m"+str(len(self.reply_list)-1)+"\033[37m"+" | 대댓글 수: "+"\033[33m"+str(len(self.rereply_list)-1) + "\033[37m"+" ||"
                print(out_str, end = "")
            else: # 대댓글
                out_str = "\r"+"\033[37m"+"|| 진행: "+"\033[33m"+str(round((self.progress/(self.date_range+1))*100, 1))+"% ("+str(self.progress) + " / " + str(self.date_range+1)+")" + "\033[37m"+" | 경과 시간: "+"\033[33m"+loadingtime + "\033[37m"+" | 날짜: "+"\033[33m"+self.trans_date+ "\033[37m"+" | url 수: "+"\033[33m"+str(len(self.urlList)) + "\033[37m"+" | "+print_type+" 수: "+"\033[33m"+str(len(self.article_list)-1)+"\033[37m"+" | 댓글 수: "+"\033[33m"+str(len(self.reply_list)-1)+"\033[37m"+" | 대댓글 수: "+"\033[36m"+str(len(self.rereply_list)-1) + "\033[37m"+" ||"
                print(out_str, end = "")
        
        elif print_type == "blog":
            print_type = "블로그"
            if signal == -1: # 날짜
                out_str = "\r"+"\033[37m"+"|| 진행: "+"\033[33m"+str(round((self.progress/(self.date_range+1))*100, 1))+"% ("+str(self.progress) + " / " + str(self.date_range+1)+")" + "\033[37m"+" | 경과 시간: "+"\033[33m"+loadingtime + "\033[37m"+" | 날짜: "+"\033[36m"+self.trans_date+ "\033[37m"+" | url 수: "+"\033[33m"+str(len(self.urlList)) + "\033[37m"+" | "+print_type+" 수: "+"\033[33m"+str(len(self.article_list)-1)+"\033[37m"+" | 댓글 수: "+"\033[33m"+str(len(self.reply_list)-1)+"\033[37m"+" ||"
                print(out_str, end = "")
            elif signal == 0: # url
                out_str = "\r"+"\033[37m"+"|| 진행: "+"\033[33m"+str(round((self.progress/(self.date_range+1))*100, 1))+"% ("+str(self.progress) + " / " + str(self.date_range+1)+")" + "\033[37m"+" | 경과 시간: "+"\033[33m"+loadingtime + "\033[37m"+" | 날짜: "+"\033[33m"+self.trans_date+ "\033[37m"+" | url 수: "+"\033[36m"+str(len(self.urlList)) + "\033[37m"+" | "+print_type+" 수: "+"\033[33m"+str(len(self.article_list)-1)+"\033[37m"+" | 댓글 수: "+"\033[33m"+str(len(self.reply_list)-1)+"\033[37m"+" ||"
                print(out_str, end = "")
            elif signal == 1: # 블로그
                out_str = "\r"+"\033[37m"+"|| 진행: "+"\033[33m"+str(round((self.progress/(self.date_range+1))*100, 1))+"% ("+str(self.progress) + " / " + str(self.date_range+1)+")" + "\033[37m"+" | 경과 시간: "+"\033[33m"+loadingtime + "\033[37m"+" | 날짜: "+"\033[33m"+self.trans_date+ "\033[37m"+" | url 수: "+"\033[33m"+str(len(self.urlList)) + "\033[37m"+" | "+print_type+" 수: "+"\033[36m"+str(len(self.article_list)-1)+"\033[37m"+" | 댓글 수: "+"\033[33m"+str(len(self.reply_list)-1)+"\033[37m"+" ||"
                print(out_str, end = "")
            else: # 댓글
                out_str = "\r"+"\033[37m"+"|| 진행: "+"\033[33m"+str(round((self.progress/(self.date_range+1))*100, 1))+"% ("+str(self.progress) + " / " + str(self.date_range+1)+")" + "\033[37m"+" | 경과 시간: "+"\033[33m"+loadingtime + "\033[37m"+" | 날짜: "+"\033[33m"+self.trans_date+ "\033[37m"+" | url 수: "+"\033[33m"+str(len(self.urlList)) + "\033[37m"+" | "+print_type+" 수: "+"\033[33m"+str(len(self.article_list)-1)+"\033[37m"+" | 댓글 수: "+"\033[36m"+str(len(self.reply_list)-1)+"\033[37m"+" ||"
                print(out_str, end = "")
        
        elif print_type == "youtube":
            print_type = "영상"
            
            if signal == -1: # 날짜
                out_str = "\r"+"\033[37m"+"|| 진행: "+"\033[33m"+str(round((self.progress/(self.date_range+1))*100, 1))+"% ("+str(self.progress) + " / " + str(self.date_range+1)+")" + "\033[37m"+" | 경과 시간: "+"\033[33m"+loadingtime + "\033[37m"+" | 날짜: "+"\033[36m"+self.trans_date+ "\033[37m"+" | url 수: "+"\033[33m"+str(len(self.urlList)) + "\033[37m"+" | "+print_type+" 수: "+"\033[33m"+str(len(self.info_list)-1)+"\033[37m"+" | 댓글 수: "+"\033[33m"+str(len(self.reply_list)-1)+"\033[37m"+" ||"
                print(out_str, end = "")
            elif signal == 0: # url
                out_str = "\r"+"\033[37m"+"|| 진행: "+"\033[33m"+str(round((self.progress/(self.date_range+1))*100, 1))+"% ("+str(self.progress) + " / " + str(self.date_range+1)+")" + "\033[37m"+" | 경과 시간: "+"\033[33m"+loadingtime + "\033[37m"+" | 날짜: "+"\033[33m"+self.trans_date+ "\033[37m"+" | url 수: "+"\033[36m"+str(len(self.urlList)) + "\033[37m"+" | "+print_type+" 수: "+"\033[33m"+str(len(self.info_list)-1)+"\033[37m"+" | 댓글 수: "+"\033[33m"+str(len(self.reply_list)-1)+"\033[37m"+" ||"
                print(out_str, end = "")
            elif signal == 1: # 블로그
                out_str = "\r"+"\033[37m"+"|| 진행: "+"\033[33m"+str(round((self.progress/(self.date_range+1))*100, 1))+"% ("+str(self.progress) + " / " + str(self.date_range+1)+")" + "\033[37m"+" | 경과 시간: "+"\033[33m"+loadingtime + "\033[37m"+" | 날짜: "+"\033[33m"+self.trans_date+ "\033[37m"+" | url 수: "+"\033[33m"+str(len(self.urlList)) + "\033[37m"+" | "+print_type+" 수: "+"\033[36m"+str(len(self.info_list)-1)+"\033[37m"+" | 댓글 수: "+"\033[33m"+str(len(self.reply_list)-1)+"\033[37m"+" ||"
                print(out_str, end = "")
            else: # 댓글
                out_str = "\r"+"\033[37m"+"|| 진행: "+"\033[33m"+str(round((self.progress/(self.date_range+1))*100, 1))+"% ("+str(self.progress) + " / " + str(self.date_range+1)+")" + "\033[37m"+" | 경과 시간: "+"\033[33m"+loadingtime + "\033[37m"+" | 날짜: "+"\033[33m"+self.trans_date+ "\033[37m"+" | url 수: "+"\033[33m"+str(len(self.urlList)) + "\033[37m"+" | "+print_type+" 수: "+"\033[33m"+str(len(self.info_list)-1)+"\033[37m"+" | 댓글 수: "+"\033[36m"+str(len(self.reply_list)-1)+"\033[37m"+" ||"
                print(out_str, end = "")
                
    def error_exception(self, e, ipchange = False):
        _, _, tb = sys.exc_info()  # tb -> traceback object
        
        if ipchange == True:     
            msg = (
            "File name: "
            + __file__
            + "\n"
            + "Error line= {}".format(tb.tb_lineno)
            + "\n"
            + "Error: {}".format(sys.exc_info()[0])
            + " "
            + str(e)
            + "\n\nip 교체됨"
            + "\n" + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        else: 
            msg = (
            "File name: "
            + __file__
            + "\n"
            + "Error line= {}".format(tb.tb_lineno)
            + "\n"
            + "Error: {}".format(sys.exc_info()[0])
            + " "
            + str(e)
            + "\n" + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
            self.error = True
            
        self.writeLog(msg)
    
    def send_email(self, loadingtime):
        
        text = "[크롤링 완료] \n"
        #text += "============================================================"
        text += "\n검색 기간: " + str(self.startYear)+"."+str(self.startMonth)+"."+str(self.startDay)+" ~ "+str(self.endYear)+"."+str(self.endMonth)+"."+str(self.endDay)
        text += "\n검색어: " + str(self.keyword)
        text += "\n옵션 번호: " + str(self.option)
        text += "\n소요 시간: " + loadingtime
        text += "\n컴퓨터: " + self.crawlcom
        text += "\n파일 링크: " + self.drive_folder_link
        #text += "\n============================================================"

        msg = MIMEMultipart()
        msg['Subject'] = "[크롤링 완료]  " + self.DBname
        msg['From'] = self.sender
        msg['To'] = self.receiver

        msg.attach(MIMEText(text, 'plain'))
        
        smtp_server = "smtp.gmail.com"
        smtp_port = 587

        # SMTP 연결 및 메일 보내기
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(self.sender, self.MailPassword)
            server.sendmail(self.sender, self.receiver, msg.as_string())
    
    def writeLog(self, msg):
        f = open(self.filedirectory + "/" + self.DBname + "/" + self.DBname + "_log.txt", "a")
        msg += "\n\n"
        f.write(msg)
        f.close()

    def random_heador(self):
        navigator = generate_navigator()
        navigator = navigator['user_agent']
        return {"User-Agent": navigator}

    def random_proxy(self):
        proxy_server = random.choice(self.proxy_list)
        if self.proxy_option.lower() == "y":
            return {"http": 'http://' + proxy_server, 'https': 'http://' + proxy_server}
        else:
            return None
        
    def clear_screen(self):
        if platform.system() == "Windows":
            os.system("cls")
        else:
            os.system("clear")

##########################################################################################################


############################################### News Crawler #############################################

    def crawl_news(self):
        
        print("\n1. 기사 \n2. 기사 + 댓글\n3. 기사 + 댓글 + 대댓글\n")
        while True:
            self.option = int(input("Option: "))
            if self.option in [1,2,3]:
                break
            else:
                print("다시 입력하세요")
        
        self.clear_screen()

        self.dbname_date = "_{}_{}".format(self.start, self.end)
        self.DBname = "Naver_News_" + self.refinedword + self.dbname_date + "_" + self.now.strftime("%m%d_%H%M")
        os.mkdir(self.filedirectory + "/" + self.DBname)  # 폴더 생성
        
        self.f = open(self.filedirectory + "/" + self.DBname + "/" + self.DBname + "_log.txt", "w+")  # Log file 생성
        self.f.close()
        
        self.article_list = [["article id", "article press", "article type", "url", "article title", "article body", "article date"]]
        self.reply_list = [["article id", "reply_id", "writer", "reply_date", "reply", "rere_count", "r_Like", "r_Bad", "r_Per_Like", 'r_Sentiment']]
        self.rereply_list = [["article id", "reply_id", "id", "rerewriter", "rereply_date", "rereply", "rere_Like", "rere_Bad"]]
        
        print("====================================================================================================================") 
        print("크롤링: 네이버 뉴스")
        print("검색 기간:", str(self.startYear)+"."+str(self.startMonth)+"."+str(self.startDay)+" ~ "+str(self.endYear)+"."+str(self.endMonth)+"."+str(self.endDay))
        print("검색어:", self.keyword)
        print("옵션 번호:", self.option)
        print("DB 저장:", self.mysql_option)
        print("컴퓨터:", self.crawlcom)
        print("저장 위치:", self.filedirectory + "/" + self.DBname)
        print("메일 수신:", self.receiver)
        print("====================================================================================================================\n")

        try:
            if self.mysql_option == 'Y':
                dbconn = News_DBConnector(self.DBpassword, self.filedirectory) # DB 생성
                dbconn.initialize(self.DBname)
            else:
                dbconn = None
            
            for i in range(self.date_range+1):
                self.progress = i
                self.trans_date = str(self.currentDate).replace("-", ".")
                self.print_status(-1, "news")
                self.get_NEWS_URLs(self.trans_date, dbconn)
                self.currentDate += self.deltaD
                
                dfarticle = pd.DataFrame(self.article_list)
                dfarticle.to_csv(self.filedirectory + "/" + self.DBname + "/" + self.DBname + "_article" + ".csv", index = False, encoding='utf-8-sig', header = False)
                
                if self.option == 2:
                    dfreply = pd.DataFrame(self.reply_list)
                    dfreply.to_csv(self.filedirectory + "/" + self.DBname + "/" + self.DBname + "_reply" + ".csv", index = False, encoding='utf-8-sig', header = False)
                
                elif self.option == 3:
                    dfreply = pd.DataFrame(self.reply_list)
                    dfrereply = pd.DataFrame(self.rereply_list)
                    dfreply.to_csv(self.filedirectory + "/" + self.DBname + "/" + self.DBname + "_reply" + ".csv", index = False, encoding='utf-8-sig', header = False)
                    dfrereply.to_csv(self.filedirectory + "/" + self.DBname + "/" + self.DBname + "_rereply" + ".csv", index = False, encoding='utf-8-sig', header = False)

            out_str = "\r"+"\033[37m"+"|| 진행: "+"\033[33m"+"100% ("+str(self.date_range+1) + " / " + str(self.date_range+1)+")"+ "\033[37m"+" | 날짜: "+"\033[33m"+self.trans_date+"\033[37m"+" | 기사 수: "+"\033[33m"+str(len(self.article_list)-1)+"\033[37m"+" | 댓글 수: "+"\033[33m"+str(len(self.reply_list)-1)+"\033[37m"+" | 대댓글 수: "+"\033[33m"+str(len(self.rereply_list)-1) + "\033[37m"+" ||"
            print(out_str, end = "")
            
            self.endtime = time.time()
            loadingsecond = self.endtime - self.starttime
            loadingtime = str(int(loadingsecond//3600))+"시간 "+str(int(loadingsecond%3600//60))+"분 "+str(int(loadingsecond%3600%60))+"초"
            
            self.upload_folder(self.filedirectory + "/" + self.DBname)
            
            print("\n\n크롤링 완료\n")
            print("분석 소요 시간:", loadingtime)
            
            self.send_email(loadingtime)
            
        except Exception as e:
            _, _, tb = sys.exc_info()  # tb -> traceback object
            msg = (
                "File name: "
                + __file__
                + "\n"
                + "Error line= {}".format(tb.tb_lineno)
                + "\n"
                + "Error: {}".format(sys.exc_info()[0])
                + " "
                + str(e)
                + "\n"
                + "Date : "
                + str(self.currentDate)
                + "\n"
                + "keyword : "
                + self.keyword
            )
            self.writeLog(msg)
            
    def parseNews(self, url, connector):
        
        base_url = "".join(
                [
                    "https://apis.naver.com/commentBox/cbox/web_naver_list_jsonp.json?ticket=news",
                    "&pool=cbox5&lang=ko&country=KR",
                    "&objectId=news{}%2C{}&categoryId=&pageSize={}&indexSize=10&groupId=&listType=OBJECT&pageType=more",
                    "&page={}&initialize=true&followSize=5&userType=&useAltSort=true&replyPageSize=20&sort={}&includeAllStatus=true&_=1696730082374",
                ]
            )
        try:
            if self.mysql_option == 'Y':
                dbconn = connector
            headers = self.random_heador()
            data = {
                "article_press": None,
                "article_type": None,
                "url": None,
                "article_title": None,
                "article_body": None,
                "article_date": None,
            }
            data["url"] = url
            
            
            while True:
                proxies = self.random_proxy()
                try:
                    res = requests.get(url, proxies = proxies, headers = headers, timeout = 3)
                    bs = BeautifulSoup(res.text, "lxml")
                    break
                except requests.exceptions.Timeout as e:
                    self.error_exception(e, True)
                except Exception as e:
                    self.error_exception(e, True)
                

            try:

                news = ''.join((i.text.replace("\n", "") for i in bs.find_all("div", {"class": "newsct_article"})))
                article_press = str(bs.find("img")).split()[1][4:].replace("\"", '') # article_press
                article_type = bs.find("em", class_="media_end_categorize_item").text # article_type
                article_title = bs.find("div", class_="media_end_head_title").text.replace("\n", " ") # article_title
                article_date = bs.find("span", {"class": "media_end_head_info_datestamp_time _ARTICLE_DATE_TIME"}).text.replace("\n", " ")

                data["article_body"] = news # article_body
                data["article_press"] = article_press
                data["article_type"] = article_type
                data["article_title"] = article_title
                data["article_date"] = article_date

                if self.mysql_option == 'Y':
                    article_id = dbconn.insertNaverArticleData(data=data)
                else:
                    article_id = 0
                    
                self.article_list.append([article_id, article_press, article_type, url, article_title, news, article_date])
                self.print_status(1, "news")
                
            except:
                return
        
            if self.option == 1: # 기사만 수집할 때 여기서 끝냄
                return
            
            oid = url[39:42]
            aid = url[43:53]
            page = 1
            
            nickname_list, replyDate_list, text_list, rere_count_list, r_like_list, r_bad_list = [], [], [], [], [], []
            parentCommentNo_list = []
            
            while True:
                try:
                    navigator = generate_navigator()
                    navigator = navigator['user_agent']
                    headers = { 
                    "User-agent":navigator, 
                    "referer":url, 
                    }  
                    
                    params = {
                            'ticket': 'news',
                            'templateId': 'default_society',
                            'pool': 'cbox5',
                            'lang': 'ko',
                            'country': 'KR',
                            'objectId': f'news{oid},{aid}',
                            'pageSize': '100',
                            'indexSize': '10',
                            'page': str(page),
                            'currentPage': '0',
                            'moreParam.direction': 'next',
                            'moreParam.prev': '10000o90000op06guicil48ars',
                            'moreParam.next': '1000050000305guog893h1re',
                            'followSize': '100',
                            'includeAllStatus': 'true',
                            'sort': 'reply'
                        }
                    try:
                        while True:
                            proxies = self.random_proxy()
                            try:
                                response = requests.get('https://apis.naver.com/commentBox/cbox/web_naver_list_jsonp.json', proxies = proxies, params=params, headers=headers, timeout = 3)
                                response.encoding = "UTF-8-sig"
                                res = response.text.replace("_callback(","")[:-2]
                                temp=json.loads(res)
                                break
                            except requests.exceptions.Timeout as e:
                                self.error_exception(e, True)
                            except Exception as e:
                                self.error_exception(e, True)
                                            
                        for comment_json in temp.get("result", {}).get("commentList", []):
                            parentCommentNo = comment_json["parentCommentNo"]
                            parentCommentNo_list.append(parentCommentNo)
                        
                        try:
                            nickname_list.extend(list(pd.DataFrame(temp['result']['commentList'])['maskedUserId']))
                            replyDate_list.extend(list(pd.DataFrame(temp['result']['commentList'])['modTime']))
                            text_list.extend(list(pd.DataFrame(temp['result']['commentList'])['contents']))
                            rere_count_list.extend(list(pd.DataFrame(temp['result']['commentList'])['replyCount']))
                            r_like_list.extend(list(pd.DataFrame(temp['result']['commentList'])['sympathyCount']))
                            r_bad_list.extend(list(pd.DataFrame(temp['result']['commentList'])['antipathyCount']))
                        except:
                            break
                        
                        if len(list(pd.DataFrame(temp['result']['commentList'])['maskedUserId'])) < 97:
                            break
                        else:
                            page += 1
                    except:
                        break
                    
                except Exception as e:
                    self.error_exception(e)
                    
            reply_idx = 0
            for i in range(len(nickname_list)):
                reply_idx += 1
                
                r_per_like = 0.0 # 댓글 긍정 지수 구하기
                r_sum_like_angry = int(r_like_list[i]) + int(r_bad_list[i])
                if r_sum_like_angry != 0:
                    r_per_like = float(int(r_like_list[i]) / r_sum_like_angry)
                    r_per_like = float(format(r_per_like, ".2f"))
                # 댓글 긍정,부정 평가
                if r_per_like > 0.5:  # 긍정
                    r_sentiment = 1
                elif r_per_like == 0:  # 무관심
                    r_sentiment = 2
                elif r_per_like < 0.5:  # 부정
                    r_sentiment = -1
                else:  # 중립
                    r_sentiment = 0
                
                if self.mysql_option == 'Y':
                    repleLastIndex = dbconn.insertNaverReplyData(
                        str(article_id),
                        str(reply_idx),
                        str(nickname_list[i]),
                        str(replyDate_list[i]),
                        str(text_list[i].replace("\n", " ")),
                        str(rere_count_list[i]),
                        str(r_like_list[i]),
                        str(r_bad_list[i]),
                        str(r_per_like),
                        str(r_sentiment),
                    )
                self.reply_list.append(
                    [str(article_id),
                    str(reply_idx),
                    str(nickname_list[i]),
                    str(replyDate_list[i]),
                    str(text_list[i].replace("\n", " ")),
                    str(rere_count_list[i]),
                    str(r_like_list[i]),
                    str(r_bad_list[i]),
                    str(r_per_like),
                    str(r_sentiment),])
                self.print_status(2, "news")
            
            if self.option == 3:
                try:
                    base_url = "".join(
                        [
                            "https://apis.naver.com/commentBox/cbox/web_naver_list_jsonp.json?ticket=news",
                            "&pool=cbox5&lang=ko&country=KR",
                            "&objectId=news{}%2C{}&categoryId=&pageSize={}&indexSize=10&groupId=&listType=OBJECT&pageType=more",
                            "&page={}&initialize=true&followSize=5&userType=&useAltSort=true&replyPageSize=20&sort={}&includeAllStatus=true&_=1696730082374",
                        ]
                    )
                    for i in range(len(parentCommentNo_list)):
                        
                        if rere_count_list[i] != 0:
                            base_url_tmp_re = (base_url.format(oid, aid, 100, 1, "reply") + "&parentCommentNo=" + parentCommentNo_list[i])
                            
                            while True:
                                proxies = self.random_proxy()
                                try:
                                    re_r = requests.get(base_url_tmp_re, headers = headers, proxies = proxies, timeout = 3)
                                    re_html = re_r.text.encode("cp949", "ignore").decode("cp949", "ignore")
                                    re_html = re_html[10:-2]
                                    re_response = json.loads(re_html)
                                    break
                                except requests.exceptions.Timeout as e:
                                    self.error_exception(e, True)
                                except Exception as e:
                                    self.error_exception(e, True)
                            
                            rereply_idx = 0
                            for rereply_json in re_response.get("result", {}).get("commentList", []):
                                rereply_idx += 1
                                re_parse_result = self._parse_news_comment(rereply_json)

                                repleLastIndex = i + 1
                                nickName2 = re_parse_result[0]
                                replyDate2 = re_parse_result[4]
                                text2 = re_parse_result[3]
                                rere_like = re_parse_result[5]
                                rere_bad = re_parse_result[6]
                                
                                try:
                                    if self.mysql_option == 'Y':
                                        dbconn.insertNaverReReplyData(
                                            str(article_id),
                                            str(repleLastIndex),
                                            str(rereply_idx),
                                            nickName2,
                                            str(replyDate2),
                                            text2.replace("\n", " "),
                                            str(rere_like),
                                            str(rere_bad),
                                        )
                                    
                                    self.rereply_list.append(
                                        [str(article_id),
                                        str(repleLastIndex),
                                        str(rereply_idx),
                                        str(nickName2),
                                        str(replyDate2),
                                        text2.replace("\n", " "),
                                        str(rere_like),
                                        str(rere_bad)])
                                    
                                    self.print_status(3, "news")
                                except:
                                    self.error_exception(e)  

                except Exception as e:
                    self.error_exception(e)  
                            
        except Exception as e:
            self.error_exception(e)

    def _parse_news_comment(self, comment_json):
            antipathy_count = comment_json["antipathyCount"]
            sympathy_count = comment_json["sympathyCount"]
            contents = (
                comment_json["contents"]
                .replace("\t", " ")
                .replace("\r", " ")
                .replace("\n", " ")
                .encode("cp949", "ignore")
                .decode("cp949", "ignore")
            )
            reg_time = comment_json["regTime"]
            user_id = (
                comment_json["userName"].encode("cp949", "ignore").decode("cp949", "ignore")
            )

            reply_count = comment_json["replyCount"]
            parentCommentNo = comment_json["parentCommentNo"]

            return (
                user_id,
                reply_count,
                parentCommentNo,
                contents,
                reg_time,
                sympathy_count,
                antipathy_count,
            )

    def get_NEWS_URLs(self, currentDate, connector):
        
        search_page_url = "https://search.naver.com/search.naver?where=news&query={}&sm=tab_srt&sort=2&photo=0&reporter_article=&pd=3&ds={}&de={}&&start={}&related=0"
        currentPage = 1
        
        self.urlList = []
        try:
            while True:
                search_page_url_tmp = search_page_url.format(self.keyword, currentDate, currentDate, currentPage)
                
                while True:
                    proxies = self.random_proxy()
                    try:
                        main_page = requests.get(search_page_url_tmp, proxies = proxies, verify = False, timeout = 3)
                        main_page = BeautifulSoup(main_page.text, "lxml") #스크랩 모듈에 url 넘김
                        site_result = main_page.select('a[class = "info"]')
                        break
                    except requests.exceptions.Timeout as e:
                        self.error_exception(e, True)
                    except Exception as e:
                        self.error_exception(e, True)
                        

                if site_result == []:
                    break

                for a in site_result: #스크랩한 데이터 중 링크만 추출
                    add_link = a['href']
                    if 'sports' not in set(add_link) and 'sid=106' not in set(add_link):
                        self.urlList.append(add_link)
                        self.print_status(0, "news")
                        
                    if add_link == None:
                        break
                
                currentPage += 10 # 다음페이지 이동
            
            for url in self.urlList:
                self.parseNews(url, connector)
        except:
            self.error_exception(e)

##########################################################################################################


############################################### Blog Crawler #############################################

    def crawl_blog(self):
        
        print("\n1. 블로그 \n2. 블로그 + 댓글\n")
        while True:
            self.option = int(input("Option: "))
            if self.option in [1,2]:
                break
            else:
                print("다시 입력하세요")
                
        self.clear_screen()
        
        self.dbname_date = "_{}_{}".format(self.start, self.end)
        self.DBname = "Naver_Blog_" + self.refinedword + self.dbname_date + "_" + self.now.strftime("%m%d_%H%M")
        os.mkdir(self.filedirectory+"/" + self.DBname)  # 폴더 생성
        
        self.f = open(self.filedirectory + "/" + self.DBname + "/" + self.DBname + "_log.txt", "w+")  # Log file 생성
        self.f.close()
        
        self.article_list = [["article id", "blog_id", "url", "article body", "article date", "good_cnt", "comment_cnt"]]
        self.reply_list = [["article id", "reply_id", "writer", "reply_date", "reply"]]
        
        print("====================================================================================================================")
        print("크롤링: 네이버 블로그")
        print("검색 기간:", str(self.startYear)+"."+str(self.startMonth)+"."+str(self.startDay)+" ~ "+str(self.endYear)+"."+str(self.endMonth)+"."+str(self.endDay))
        print("검색어:", self.keyword)
        print("옵션 번호:", self.option)
        print("DB 저장:", self.mysql_option)
        print("컴퓨터:", self.crawlcom)
        print("저장 위치:", self.filedirectory + "/" + self.DBname)
        print("메일 수신:", self.receiver)
        print("====================================================================================================================\n")
        
        try:
            if self.mysql_option == 'Y':
                dbconn = News_DBConnector(self.DBpassword, self.filedirectory) # DB 생성
                dbconn.initialize(self.DBname)
            else:
                dbconn = None
            
            for i in range(self.date_range+1):
                self.progress = i
                self.trans_date = str(self.currentDate)
                self.print_status(-1, "blog")
                self.get_BLOG_URLs(self.trans_date, dbconn)
                self.currentDate += self.deltaD
                
                dfarticle = pd.DataFrame(self.article_list)
                dfarticle.to_csv(self.filedirectory + "/" + self.DBname + "/" + self.DBname + "_article" + ".csv", index = False, encoding='utf-8-sig', header = False)
                
                if self.option == 2:
                    dfreply = pd.DataFrame(self.reply_list)
                    dfreply.to_csv(self.filedirectory + "/" + self.DBname + "/" + self.DBname + "_reply" + ".csv", index = False, encoding='utf-8-sig', header = False)
        
            out_str = "\r"+"\033[37m"+"|| 진행: "+"\033[33m"+"100% ("+str(self.date_range+1) + " / " + str(self.date_range+1)+")"+ "\033[37m"+" | 날짜: "+"\033[33m"+self.trans_date+"\033[37m"+" | 블로그 수: "+"\033[33m"+str(len(self.article_list)-1)+"\033[37m"+" | 댓글 수: "+"\033[33m"+str(len(self.reply_list)-1)+ "\033[37m"+" ||"
            print(out_str, end = "")
            
            self.endtime = time.time()
            loadingsecond = self.endtime - self.starttime
            loadingtime = str(int(loadingsecond//3600))+"시간 "+str(int(loadingsecond%3600//60))+"분 "+str(int(loadingsecond%3600%60))+"초"
            
            self.upload_folder(self.filedirectory + "/" + self.DBname)
            
            print("\n\n크롤링 완료\n")
            print("분석 소요 시간:", loadingtime)
            
            self.send_email(loadingtime)
            
        except Exception as e:
            _, _, tb = sys.exc_info()  # tb -> traceback object
            msg = (
                "File name: "
                + __file__
                + "\n"
                + "Error line= {}".format(tb.tb_lineno)
                + "\n"
                + "Error: {}".format(sys.exc_info()[0])
                + " "
                + str(e)
                + "\n"
                + "Date : "
                + str(self.currentDate)
                + "\n"
                + "keyword : "
                + self.keyword
            )
            self.writeLog(msg)
            
    def parseBlog(self, url, connector):   
        try:
            original_url = url
            if self.mysql_option == 'Y':
                dbconn = connector
            article_data = {
                "blog_ID": None,
                "url": None,
                "article_body": None,
                "article_date": None,
                "good_cnt": None,
                "comment_cnt": None
            }
            
            split_url = url.split("/")
            blogID, logNo = split_url[3], split_url[4]
            
            url = "https://blog.naver.com/PostView.naver?blogId={}&logNo={}&redirect=Dlog&widgetTypeCall=false&directAccess=false".format(blogID, logNo)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                "referer" : "https://blog.naver.com/SympathyHistoryList.naver?blogId={}&logNo={}".format(blogID, logNo)
            }
            
        
            while True:
                proxies = self.random_proxy()
                try:
                    response = requests.get(url, headers = headers, proxies = proxies, timeout = 3)
                    soup = BeautifulSoup(response.text, "html.parser")
                    
                    script_tag = soup.find('script', string=re.compile(r'var\s+blogNo\s*=\s*\'(\d+)\''))
                    blogNo = re.search(r'var\s+blogNo\s*=\s* \'(\d+)\'', script_tag.text).group(1)
                    objectID = f'{blogNo}_201_{logNo}'
                    try:
                        good_cnt_url = "https://blog.naver.com/api/blogs/{}/posts/{}/sympathy-users".format(blogID, logNo)
                        good_cnt = json.loads(BeautifulSoup(requests.get(good_cnt_url, headers = headers, proxies = proxies, timeout = 3).text, "html.parser").text)['result']['totalCount']

                        comment_cnt_url = "https://apis.naver.com/commentBox/cbox/web_naver_list_jsonp.json?ticket=blog&pool=blogid&lang=ko&country=&objectId={}&groupId={}".format(objectID, blogNo)
                        comment_cnt = json.loads(requests.get(comment_cnt_url, headers = headers, proxies = proxies, timeout = 3).text)['result']['count']['comment']
                    except:
                        good_cnt = 0
                        comment_cnt = 0
                        break
                    break
                except requests.exceptions.Timeout as e:
                    self.error_exception(e, True)
                except Exception as e:
                    self.error_exception(e, True)
                    
                
            try:
                article = "".join([i.text.replace("\n", "").replace("\t", "").replace("\u200b", "") for i in soup.select("div[class = 'se-module se-module-text']")])
                date = "".join([i.text for i in soup.select("span[class = 'se_publishDate pcol2']")])
                
                if article == "":
                    return
                article_data["blog_ID"] = str(blogID)
                article_data["url"] = str(original_url)
                article_data["article_body"] = str(article)
                article_data["article_date"] = str(date)
                article_data["good_cnt"] = str(good_cnt)
                article_data["comment_cnt"] = str(comment_cnt)
                
                if self.mysql_option == 'Y':
                    article_id = dbconn.insertNaverArticleData(data = article_data)
                else:
                    article_id = 0
                self.article_list.append([article_id, blogID, original_url, article, date, good_cnt, comment_cnt])
                self.print_status(1, "blog")
            
            except:
                return
            
            if self.option == 1 or comment_cnt == 0:
                return
            
            
            page = 1
            
            nickname_list, replyDate_list, text_list= [], [], []
            
            while True:
                try:
                    navigator = generate_navigator()
                    navigator = navigator['user_agent']
                    headers = {
                        'user-agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'referer': url}
                    try:
                        while True:
                            proxies = self.random_proxy()
                            try: 
                                params = {
                                        'ticket': "blog",
                                        'templateId': 'default',
                                        'pool': 'blogid',
                                        'lang': 'ko',
                                        'country': 'KR',
                                        'objectId': objectID,
                                        'groupId': blogNo,
                                        'pageSize': '50',
                                        'indexSize': '10',
                                        'page': str(page),
                                        'morePage.prev': '051v2o4l34sgr1t0txuehz9fxg',
                                        'morePage.next': '051sz9hwab3fe1t0w1916s34yt',
                                }
                                response = requests.get('https://apis.naver.com/commentBox/cbox/web_naver_list_jsonp.json', params=params, headers=headers, proxies = proxies, timeout = 3)
                                response.encoding = "UTF-8-sig"
                                break
                            except requests.exceptions.Timeout as e:
                                self.error_exception(e, True)
                            except Exception as e:
                                self.error_exception(e, True)
                                
                        try:
                            temp=json.loads(response.text)
                            nickname_list.extend(list(pd.DataFrame(temp['result']['commentList'])['userName']))
                            replyDate_list.extend(list(pd.DataFrame(temp['result']['commentList'])['modTime']))
                            text_list.extend(list(pd.DataFrame(temp['result']['commentList'])['contents']))
                        except:
                            break
                        
                        if len(list(pd.DataFrame(temp['result']['commentList'])['userName'])) < 50:
                            break
                        else:
                            page += 1
                    except:
                        break
                    
                except Exception as e:
                    self.error_exception(e)
                
            reply_idx = 0
            for i in range(len(nickname_list)):
                if str(nickname_list[i]) != "":
                    reply_idx += 1
                    try:
                        if self.mysql_option == 'Y':
                            dbconn.insertNaverReplyData(
                                str(article_id),
                                str(reply_idx),
                                str(nickname_list[i]),
                                str(replyDate_list[i]),
                                str(text_list[i].replace("\n", " ").replace("\r", "").replace("<br>"," "))
                            )
                    except Exception as e:
                        self.error_exception(e)
        
                    self.reply_list.append([
                        str(article_id),
                        str(reply_idx),
                        str(nickname_list[i]),
                        str(replyDate_list[i]),
                        str(text_list[i].replace("\n", " ").replace("\r", "").replace("<br>"," ")),
                    ])
                    self.print_status(2, "blog")
                
        except Exception as e:
            self.error_exception(e)
            
    def get_BLOG_URLs(self, currentDate, connector):
        
        self.urlList = []
        currentPage = 1
        
        try:
            while True:
                
                search_page_url = "https://section.blog.naver.com/ajax/SearchList.naver?countPerPage=20&currentPage={}&endDate={}&keyword={}&orderBy=recentdate&startDate={}&type=post".format(str(currentPage), currentDate, self.keyword, currentDate)
                referer = "https://section.blog.naver.com/Search/Post.naver?pageNo={}".format(str(currentPage))
                
                header = {
                'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'referer': referer}
                
                tempList = []
                
                while True:
                    proxies = self.random_proxy()
                    try:
                        main_page = requests.get(search_page_url, headers = header, proxies = proxies, timeout = 3).text[6:]
                        break
                    except requests.exceptions.Timeout as e:
                        self.error_exception(e, True)
                    except Exception as e:
                        self.error_exception(e, True)
                
                try:
                    temp = json.loads(main_page)
                    searchList = temp["result"]['searchList']
                except:
                    break
                
                for i in searchList:
                    tempList.append(i['postUrl'])
                
                if set(tempList) <= set(self.urlList):
                    break
                
                self.urlList.extend(tempList)
                self.print_status(0, "blog")
                
                if len(tempList) < 20:
                    break
                
                self.print_status(0, "blog")
                
                currentPage += 1
                
            for url in self.urlList:
                self.parseBlog(url, connector)  
                
        except Exception as e:
            self.error_exception(e)

##########################################################################################################

############################################## YouTube Crawler ############################################

    def crawl_youtube(self):
        
        print("\n1. 영상 정보 \n2. 영상 정보 + 댓글\n")
        while True:
            self.option = int(input("Option: "))
            if self.option in [1,2]:
                break
            else:
                print("다시 입력하세요")
        
        self.clear_screen()
        
        self.dbname_date = "_{}_{}".format(self.start, self.end)
        self.DBname = "YouTube_" + self.refinedword + self.dbname_date + "_" + self.now.strftime("%m%d_%H%M")
        os.mkdir(self.filedirectory + "/" + self.DBname)  # 폴더 생성
        
        self.f = open(self.filedirectory + "/" + self.DBname + "/" + self.DBname + "_log.txt", "w+")  # Log file 생성
        self.f.close()
        
        self.info_list = [["info_id", "channel", "video_url", "video_title", "video_description", "video_date", "view_count", "like_count", "comment_count"]]
        self.reply_list = [["info_id", "reply_id", "writer", "reply_date", "reply", "r_Like", "rere_count"]]
        self.bigurlList = []

        print("====================================================================================================================") 
        print("크롤링: 유튜브")
        print("검색 기간:", str(self.startYear)+"."+str(self.startMonth)+"."+str(self.startDay)+" ~ "+str(self.endYear)+"."+str(self.endMonth)+"."+str(self.endDay))
        print("검색어:", self.keyword)
        print("옵션 번호:", self.option)
        print("DB 저장:", self.mysql_option)
        print("컴퓨터:", self.crawlcom)
        print("저장 위치:", self.filedirectory + "/" + self.DBname)
        print("메일 수신:", self.receiver)
        print("====================================================================================================================\n")

        try:
            if self.mysql_option == 'Y':
                dbconn = News_DBConnector(self.DBpassword, self.filedirectory) # DB 생성
                dbconn.initialize(self.DBname)
            else:
                dbconn = None
            
            for i in range(self.date_range+1):
                self.progress = i
                self.trans_date = str(self.currentDate)
                self.print_status(-1, "youtube")
                self.get_YOUTUBE_URLs(str(self.currentDate.strftime("%m/%d/%Y")), dbconn)
                self.currentDate += self.deltaD
                
                
                dfinfo = pd.DataFrame(self.info_list)
                dfinfo.to_csv(self.filedirectory + "/" + self.DBname + "/" + self.DBname + "_info" + ".csv", index = False, encoding='utf-8-sig', header = False)
            
                if self.option == 2:
                    dfreply = pd.DataFrame(self.reply_list)
                    dfreply.to_csv(self.filedirectory + "/" + self.DBname + "/" + self.DBname + "_reply" + ".csv", index = False, encoding='utf-8-sig', header = False)
        
            self.endtime = time.time()
            loadingsecond = self.endtime - self.starttime
            loadingtime = str(int(loadingsecond//3600))+"시간 "+str(int(loadingsecond%3600//60))+"분 "+str(int(loadingsecond%3600%60))+"초"
            
            self.upload_folder(self.filedirectory + "/" + self.DBname)
            
            print("\n\n크롤링 완료\n")
            print("분석 소요 시간:", loadingtime)
            
            self.send_email(loadingtime)
            
        except Exception as e:
            _, _, tb = sys.exc_info()  # tb -> traceback object
            msg = (
                "File name: "
                + __file__
                + "\n"
                + "Error line= {}".format(tb.tb_lineno)
                + "\n"
                + "Error: {}".format(sys.exc_info()[0])
                + " "
                + str(e)
                + "\n"
                + "Date : "
                + str(self.currentDate)
                + "\n"
                + "keyword : "
                + self.keyword
            )
            self.writeLog(msg)
        
    def parseYoutube(self, url, connector):
        try:
            if self.mysql_option == 'Y':
                dbconn = connector
            #print(url)
            if url[8] == 'm':
                youtube_info = url[30:]
            else:
                youtube_info = url[32:]
            
            ######################################### selenium #########################################
            try:
                sele_proxy = random.choice(self.proxy_list)
                sele_proxy = "--proxy-server="+str(sele_proxy)
                header = self.random_heador()

                options = Options()
                options.add_argument('headless')
                options.add_argument(sele_proxy)
                options.add_argument(str(header))
                options.add_experimental_option('excludeSwitches', ['enable-logging'])
                
                #options.add_argument("--start-maximized") #전체화면으로

                crawler = webdriver.Chrome(options=options)
                crawler.implicitly_wait(1) #타임슬립 유사 기능
                #hadzy 접속
                crawler.get("https://hadzy.com/")
                #동의버튼 누르기
                accept_all = crawler.find_element('xpath', '/html/body/div[2]/div[3]/div/div[3]/button/span[1]')
                accept_all.click()

                #URL 입력
                enter_url = crawler.find_element('xpath', '//*[@id="root"]/div/div[2]/form/div/input')
                enter_url.click()
                enter_url.send_keys(url) #유튜브 URL 입력
                enter_url.send_keys(Keys.ENTER)

                #Load Data 클릭
                load_data = crawler.find_element('xpath', '//*[@id="root"]/div/div[2]/div[2]/button')
                load_data.click()

                #로드가 완료되면 나타나는 요소 정의(View Comments 단추)
                ld_complete_xpath = '//*[@id="root"]/div/div[2]/div[2]/a[1]/button/span[1]'

                #로드 될 때까지 최대 30초 대기
                WebDriverWait(crawler, 30).until(
                    EC.presence_of_element_located((By.XPATH, ld_complete_xpath)))

                # View Comments 또는 View Statictics 클릭
                crawler.quit()
            except:
                pass
        
            ############################################################################################
            
            headers = self.random_heador()
            info_api_url = "https://hadzy.com/api/videos/{}".format(youtube_info)
            
            while True:
                proxies = self.random_proxy()
                try:
                    main_page = requests.get(info_api_url, headers = headers, proxies = proxies, timeout = 3)
                    break
                except requests.exceptions.Timeout as e:
                    self.error_exception(e, True)
                except Exception as e:
                    self.error_exception(e, True)
            
            try:
                temp = json.loads(main_page.text)
                channel = temp['items'][0]['snippet']['channelTitle'] # 채널 이름
                video_url = url # url
                video_title = temp['items'][0]['snippet']['title'].replace("\n", " ").replace("\r", "").replace("\t", "").replace("<br>"," ") # 영상 제목
                video_description = temp['items'][0]['snippet']['description'].replace("\n","").replace("\t","").replace("\r", "").replace("<br>"," ") # 영상 설명
                video_date = temp['items'][0]['snippet']['publishedAt']  # 영상 날짜
                view_count = temp['items'][0]['statistics']['viewCount']  # 조회수
                like_count = temp['items'][0]['statistics']['likeCount']  # 좋아요
                comment_count = temp['items'][0]['statistics']['commentCount']  # 댓글 수
            except:
                return
                
            info_data = {
                "info_id": None, 
                "channel": str(channel),
                "video_url": str(video_url),
                "video_title": str(video_title),
                "video_description": str(video_description),
                "video_date": str(video_date),
                "view_count": str(view_count),
                "like_count": str(like_count),
                "comment_count": str(comment_count)
            }
            
            info_id = dbconn.insertYouTubeInfoData(info_data)
            
            self.info_list.append([info_id, channel, video_url, video_title, video_description, video_date, view_count, like_count, comment_count])
            self.print_status(1, "youtube")
            
            if comment_count == None:
                return
            
            if self.option == 1 or len(comment_count) == 0:
                return
            
            page = 0
            reply_idx = 0
            while True:
                try:
                    comment_api_url = "https://hadzy.com/api/comments/{}?page={}%20%20%20%20%20%20&size=10&sortBy=publishedAt&direction=asc%20%20%20%20%20%20&searchTerms=&author=".format(youtube_info, page)

                    headers = self.random_heador()
                    
                    while True:
                        proxies = self.random_proxy()
                        try:
                            main_page = requests.get(comment_api_url, headers = headers, proxies = proxies, timeout = 3)
                            break
                        except requests.exceptions.Timeout as e:
                            self.error_exception(e, True)
                        except Exception as e:
                            self.error_exception(e, True)
                            
                    try:
                        temp = json.loads(main_page.text)
                        #print(temp)
                    except:
                        return
                    
                    if len(temp["content"]) == 0:
                        break
                    
                    for i in range(len(temp['content'])):
                        reply_idx += 1
                        try:
                            dbconn.insertYouTubeReplyData(
                                info_id,
                                reply_idx,
                                str(temp['content'][i]['authorDisplayName']),
                                str(temp['content'][i]['publishedAt']),
                                str(temp['content'][i]['textDisplay'].replace("\n", " ").replace("\r", "").replace("\t", "").replace("<br>"," ")),
                                str(temp['content'][i]['likeCount']),
                                str(temp['content'][i]['totalReplyCount'])
                            )

                        except Exception as e:
                            self.error_exception(e)
                            
                        self.reply_list.append(
                            [
                                info_id,
                                reply_idx,
                                temp['content'][i]['authorDisplayName'], # 작성자
                                temp['content'][i]['publishedAt'], # 작성일
                                temp['content'][i]['textDisplay'].replace("\n", " ").replace("\r", "").replace("\t", "").replace("<br>"," "), # 작성글
                                temp['content'][i]['likeCount'], # 좋아요 수
                                temp['content'][i]['totalReplyCount'] # 총 대댓글 수
                                
                            ]
                        )
                        self.print_status(2, "youtube")
                    page += 1 
                    
                except Exception as e:
                    self.error_exception(e)  
                    
        except Exception as e:
            self.error_exception(e)  
        
    def get_YOUTUBE_URLs(self, currentDate, connector):
        
        currentPage = 0
        
        self.urlList = []
        try:
            while True:
                search_page_url = "https://www.google.com/search?q=intitle:{}&tbm=vid&tbs=cdr:1,cd_min:{},cd_max:{}&as_sitesearch=youtube.com&start={}".format(self.keyword, currentDate, currentDate, currentPage)
                header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                cookie = {'CONSENT' : 'YES'}
                
                while True:
                    proxies = self.random_proxy()
                    try:
                        main_page = requests.get(search_page_url, headers = header, proxies = proxies, cookies = cookie, timeout = 3)
                        main_page = BeautifulSoup(main_page.text, "lxml")
                        site_result = main_page.select("a[jsname = 'UWckNb']")
                        break
                    except requests.exceptions.Timeout as e:
                        self.error_exception(e, True)
                    except Exception as e:
                        self.error_exception(e, True)
                        
                if site_result == []:
                    break
                
                for a in site_result: #스크랩한 데이터 중 링크만 추출
                    add_link = a['href']
                    if "playlist" not in add_link and add_link not in self.bigurlList:
                        self.urlList.append(add_link)
                        self.bigurlList.append(add_link)
                        self.print_status(0, "youtube")
                
                    if add_link == None:
                        break
                
                currentPage += 10
            
            for url in self.urlList:
                self.parseYoutube(url, connector)
                
        except Exception as e:
            self.error_exception(e)

###########################################################################################################

################################################ mySQL DB ################################################

class News_DBConnector:
    
    def __init__(self, password, filedirectory):
        self.filedirectory = filedirectory
        self.password = password
        try:
            self.conn = pymysql.connect(host='127.0.0.1', user='root', password=self.password, charset='utf8mb4', read_timeout = 2, write_timeout = 2, connect_timeout = 2)    
        except Exception as e:
            print('Connection Error : ', e)
        return
    
    def error_exception(self, e, ipchange = False):
        _, _, tb = sys.exc_info()  # tb -> traceback object
        
        if ipchange == True:
            msg = (
            "File name: "
            + __file__
            + "\n"
            + "Error line= {}".format(tb.tb_lineno)
            + "\n"
            + "Error: {}".format(sys.exc_info()[0])
            + " "
            + str(e)
            + "\n\nip 교체됨"
        )
            
        else: 
            msg = (
            "File name: "
            + __file__
            + "\n"
            + "Error line= {}".format(tb.tb_lineno)
            + "\n"
            + "Error: {}".format(sys.exc_info()[0])
            + " "
            + str(e)
        )
            self.error = True
            
        self.writeLog(msg)
        
    def writeLog(self, msg):
        f = open(self.filedirectory + "/" + self.DBname + "/" + self.DBname + "_log.txt", "a")
        msg += "\n\n"
        f.write(msg)
        f.close()
    
    def initialize(self, dbname):
        
        self.createNaverDatabase(dbname)
        self.createNaverArticleTable(dbname)
        self.createNaverReplyTable(dbname)
        self.createNaverReReplyTable(dbname)
        self.DBname = dbname
    
    def connect(self):
        try:
            return pymysql.connect(host='127.0.0.1', user='root', password=self.password, charset='utf8mb4', read_timeout = 2, write_timeout = 2, connect_timeout = 2)    
        except Exception as e:
            self.error_exception(e)
            raise  # 연결 실패시 예외를 다시 발생시켜 호출자에게 알림

    def setDBName(self, name):
        self.dbname = name

    #Naver뉴스 DB생성(NaverNews_DB) 함수
    def createNaverDatabase(self,dbname):
        try:
            self.dbname = dbname
            self.connect()
            curs = self.conn.cursor() #cursor = 데이터베이스 쿼리를 실행하고 결과를 관리하는 객체, curs변수에 생성
            #NaverNews_DB를 생성하는 쿼리
            query = """CREATE DATABASE """+dbname # 데이터 베이스 생성
            curs.execute(query) # query를 excute
            print('DB를 생성. DB_NAME :' , dbname)
            print("")
            self.conn.commit()    

            # NaverNews_DB의 문자세트를 utf8로 변환
            query = """ALTER DATABASE """+ dbname + """ CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;"""
            curs.execute(query)
            self.conn.commit()
            self.conn.close()

        except Exception as e:
            self.error_exception(e)
        finally:
            if conn:
                conn.close()
                
    #Naver뉴스 Table 생성 함수
    def createNaverArticleTable(self, dbname):
        self.connect()
        curs = self.conn.cursor()
        query = """use """+dbname
        curs.execute(query)
        self.conn.commit()
        #NaverNews라는 ID, URL, TITLE 등등을 포함하는 테이블을 생성
        query = """create table naver_articles(   
                                            article_id int not null auto_increment primary key,
                                            article_press varchar(50),
                                            article_type varchar(11), 
                                            url text, 
                                            article_title text, 
                                            article_body text,
                                            article_date varchar(50)
                                            )"""
        try:
            curs.execute(query)
            self.conn.commit()
            query = """ALTER TABLE naver_articles CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;"""
            curs.execute(query)
            self.conn.commit()
            self.conn.close()
        except Exception as e:
            self.error_exception(e)
        finally:
            if conn:
                conn.close()

    #Naver뉴스 댓글 Table 생성 함수
    def createNaverReplyTable(self,dbname):
        self.connect()
        curs = self.conn.cursor()
        query = """use """+dbname
        curs.execute(query)
        self.conn.commit()
        #NaverNews라는 ID, URL, TITLE 등등을 포함하는 테이블을 생성
        query = """create table naver_replies(   
                                            article_id int not null, 
                                            reply_id int not null auto_increment primary key, 
                                            writer varchar(512),
                                            reply_date varchar(50),
                                            reply text, 
                                            rere_count int,
                                            r_Like int, 
                                            r_Bad int,
                                            r_Per_Like float,
                                            r_Sentiment int,
                                            FOREIGN KEY(article_id) REFERENCES naver_articles(article_id) ON UPDATE CASCADE ON DELETE CASCADE
                                            )"""

        try:
            curs.execute(query)
            self.conn.commit()
            query = """ALTER TABLE naver_replies CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;"""
            curs.execute(query)
            self.conn.commit()
            self.conn.close()
        except Exception as e:
            self.error_exception(e)
        finally:
            if conn:
                conn.close()

    #Naver뉴스 대댓글 Table 생성 함수
    def createNaverReReplyTable(self,dbname):
        self.connect()
        curs = self.conn.cursor()
        query = """use """+dbname
        curs.execute(query)
        self.conn.commit()
        #NaverNews라는 ID, URL, TITLE 등등을 포함하는 테이블을 생성
        query = """create table naver_rereplies(   
                                            article_id int not null, 
                                            reply_id int not null, 
                                            id int not null auto_increment primary key, 
                                            rerewriter varchar(512), 
                                            rereply_date varchar(50),
                                            rere text,
                                            rere_like int,
                                            rere_bad int,
                                            FOREIGN KEY(article_id) REFERENCES Naver_Articles(article_id) ON UPDATE CASCADE ON DELETE CASCADE,
                                            FOREIGN KEY(reply_id) REFERENCES Naver_Replies(reply_id) ON UPDATE CASCADE ON DELETE CASCADE
                                            )"""

        try:
            curs.execute(query)
            self.conn.commit()
            query = """ALTER TABLE naver_rereplies CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;"""
            curs.execute(query)
            self.conn.commit()
            self.conn.close()
        except Exception as e:
            self.error_exception(e)
        finally:
            if conn:
                conn.close()
    
    #네이버 댓글 DB입력
    def insertNaverReplyData(self, Article_ID, Reply_ID, Writer, ReplyDate ,Reply,ReRe_count,R_Like,R_Bad,R_Per_Like,R_Sentiment):
        try:
            self.connect()
            curs = self.conn.cursor()
            query = """insert into """ +self.dbname+ """.Naver_Replies(Article_ID, 
                                                    Writer, 
                                                    reply_date, 
                                                    Reply,
                                                    ReRe_count,
                                                    R_Like,
                                                    R_Bad,
                                                    R_Per_Like,
                                                    R_Sentiment) values (%s ,%s, %s, %s, %s, %s, %s, %s, %s)"""
            curs.execute(query, (Article_ID, Writer, ReplyDate, Reply, ReRe_count, R_Like, R_Bad, R_Per_Like, R_Sentiment))
            self.conn.commit()
            self.conn.close()
            lastIndex = curs.lastrowid
            return lastIndex
        except Exception as e:
            self.error_exception(e)
        finally:
            if conn:
                conn.close()
        

    #네이버 대댓글 DB입력
    def insertNaverReReplyData(self, Article_ID, Reply_ID, ReReply_ID, ReReWriter,ReReDate, ReRe, ReRe_Like, ReRe_Bad):
        try:
            self.connect()
            curs = self.conn.cursor()        
            query = """insert into """ +self.dbname+ """.Naver_ReReplies(   
                                                Article_ID,
                                                Reply_ID,
                                                ReReWriter,
                                                rereply_date,
                                                ReRe,
                                                ReRe_Like,
                                                ReRe_Bad) values (%s ,%s , %s, %s, %s, %s, %s)"""
            curs.execute(query, (Article_ID, Reply_ID, ReReWriter,ReReDate,ReRe, ReRe_Like, ReRe_Bad))
            self.conn.commit()
            self.conn.close()
        except Exception as e:
            self.error_exception(e)
        finally:
            if conn:
                conn.close()
        

    #네이버 기사 데이터 추가
    def insertNaverArticleData(self, data):
        try:
            self.connect()
            curs = self.conn.cursor()
            lastIndex = -1 
            query = """ insert into """ +self.dbname+ """.naver_articles (
            article_press, 
            article_type, 
            url, 
            article_title, 
            article_body, 
            article_date
            ) select * from ( select %s as a, %s as b, %s as c, %s as d, %s as e, %s as f) as tmp"""
                        
            
            
            curs.execute(query, (data['article_press'], 
                                data['article_type'], 
                                data['url'], 
                                data['article_title'], 
                                data['article_body'], 
                                data['article_date']))
            lastIndex = curs.lastrowid
            self.conn.commit()
            self.conn.close()
            
            return lastIndex
        
        except Exception as e:
            self.error_exception(e)
        finally:
            if conn:
                conn.close()

class Blog_DBConnector:
    
    def __init__(self, password, filedirectory):
        self.password = password
        self.filedirectory = filedirectory
        try:
            self.conn = pymysql.connect(host='127.0.0.1', user='root', password=self.password, charset='utf8mb4', read_timeout = 2, write_timeout = 2, connect_timeout = 2)    
        except Exception as e:
            print('Connection Error : ', e)
        return
    
    def error_exception(self, e, ipchange = False):
        _, _, tb = sys.exc_info()  # tb -> traceback object
        
        if ipchange == True:
            msg = (
            "File name: "
            + __file__
            + "\n"
            + "Error line= {}".format(tb.tb_lineno)
            + "\n"
            + "Error: {}".format(sys.exc_info()[0])
            + " "
            + str(e)
            + "\n\nip 교체됨"
        )
            
        else: 
            msg = (
            "File name: "
            + __file__
            + "\n"
            + "Error line= {}".format(tb.tb_lineno)
            + "\n"
            + "Error: {}".format(sys.exc_info()[0])
            + " "
            + str(e)
        )
            self.error = True
            
        self.writeLog(msg)
        
    def writeLog(self, msg):
        f = open(self.filedirectory + "/" + self.DBname + "/" + self.DBname + "_log.txt", "a")
        msg += "\n\n"
        f.write(msg)
        f.close()
    
    def initialize(self, dbname):
        
        self.createNaverDatabase(dbname)
        self.createNaverArticleTable(dbname)
        self.createNaverReplyTable(dbname)
        self.DBname = dbname
    
    def connect(self):
        try:
            self.conn = pymysql.connect(host='127.0.0.1', user='root', password=self.password, charset='utf8mb4', read_timeout = 2, write_timeout = 2, connect_timeout = 2)    
        except Exception as e:
            self.error_exception(e)
            raise  # 연결 실패시 예외를 다시 발생시켜 호출자에게 알림

    #Naver블로그 DB생성(NaverNews_DB) 함수
    def createNaverDatabase(self,dbname):
        try:
            self.dbname = dbname
            self.connect()
            curs = self.conn.cursor() #cursor = 데이터베이스 쿼리를 실행하고 결과를 관리하는 객체, curs변수에 생성
            #NaverNews_DB를 생성하는 쿼리
            query = """CREATE DATABASE """+dbname # 데이터 베이스 생성
            curs.execute(query) # query를 excute
            print('DB를 생성. DB_NAME :' , dbname)
            print("")
            self.conn.commit()    

            # NaverNews_DB의 문자세트를 utf8로 변환
            query = """ALTER DATABASE """+ dbname + """ CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;"""
            curs.execute(query)
            self.conn.commit()
            self.conn.close()

        except Exception as e:
            self.error_exception(e)
        finally:
            if conn:
                conn.close()

    #Naver블로그 Table 생성 함수
    def createNaverArticleTable(self, dbname):
        self.connect()
        curs = self.conn.cursor()
        query = """use """+dbname
        curs.execute(query)
        self.conn.commit()
        #NaverNews라는 ID, URL, TITLE 등등을 포함하는 테이블을 생성
        query = """create table naver_articles(   
                                            article_id int not null auto_increment primary key,
                                            blog_id text,
                                            url text, 
                                            article_body text,
                                            article_date varchar(50),
                                            good_cnt varchar(50),
                                            comment_cnt varchar(50)
                                            )"""
        try:
            curs.execute(query)
            self.conn.commit()
            query = """ALTER TABLE naver_articles CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;"""
            curs.execute(query)
            self.conn.commit()
            self.conn.close()
        except Exception as e:
            self.error_exception(e)
        finally:
            if conn:
                conn.close()

    #Naver블로그 댓글 Table 생성 함수
    def createNaverReplyTable(self,dbname):
        self.connect()
        curs = self.conn.cursor()
        query = """use """+dbname
        curs.execute(query)
        self.conn.commit()
        #NaverNews라는 ID, URL, TITLE 등등을 포함하는 테이블을 생성
        query = """create table naver_replies(   
                                            article_id int not null, 
                                            reply_id int not null auto_increment primary key, 
                                            writer varchar(512),
                                            reply_date varchar(50),
                                            reply text, 
                                            FOREIGN KEY(article_id) REFERENCES naver_articles(article_id) ON UPDATE CASCADE ON DELETE CASCADE
                                            )"""

        try:
            curs.execute(query)
            self.conn.commit()
            query = """ALTER TABLE naver_replies CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;"""
            curs.execute(query)
            self.conn.commit()
            self.conn.close()
        
        except Exception as e:
            self.error_exception(e)
        finally:
            if conn:
                conn.close()

    #네이버 블로그 댓글 DB입력
    def insertNaverReplyData(self, Article_ID, Reply_ID, Writer, ReplyDate ,Reply):
        try:
            self.connect()
            curs = self.conn.cursor()
            query = """insert into """ +self.dbname+ """.Naver_Replies(Article_ID, 
                                                    Writer, 
                                                    reply_date, 
                                                    Reply
                                                    ) values (%s ,%s, %s, %s)"""
            curs.execute(query, (Article_ID, Writer, ReplyDate, Reply))
            self.conn.commit()
            self.conn.close()
            lastIndex = curs.lastrowid
            return lastIndex
        except Exception as e:
            self.error_exception(e)
        finally:
            if conn:
                conn.close()

    #네이버 블로그 데이터 추가
    def insertNaverArticleData(self, data):
        try:
            self.connect()
            curs = self.conn.cursor()
            lastIndex = -1 
            query = """ insert into """ +self.dbname+ """.naver_articles (
            blog_ID,
            url, 
            article_body, 
            article_date,
            good_cnt,
            comment_cnt
            ) select * from ( select %s as a, %s as b, %s as c, %s as d, %s as e, %s as f) as tmp"""
                        
            curs.execute(query, (
                                data['blog_ID'],
                                data['url'], 
                                data['article_body'], 
                                data['article_date'], 
                                data['good_cnt'],
                                data['comment_cnt']
                                ))
            lastIndex = curs.lastrowid
            self.conn.commit()
            self.conn.close()
            
            return lastIndex
        
        except Exception as e:
            self.error_exception(e)
        finally:
            if conn:
                conn.close()

class YouTube_DBConnector:
    
    global conn
    dbname = ''
    
    def __init__(self, password, filedirectory):
        self.filedirectory = filedirectory
        self.password = password
        try:
            self.conn = pymysql.connect(host='127.0.0.1', user='root', password=self.password, charset='utf8mb4', read_timeout = 2, write_timeout = 2, connect_timeout = 2)    
        except Exception as e:
            print('Connection Error : ', e)
        return
    
    def error_exception(self, e, ipchange = False):
        _, _, tb = sys.exc_info()  # tb -> traceback object
        
        if ipchange == True:
            msg = (
            "File name: "
            + __file__
            + "\n"
            + "Error line= {}".format(tb.tb_lineno)
            + "\n"
            + "Error: {}".format(sys.exc_info()[0])
            + " "
            + str(e)
            + "\n\nip 교체됨"
        )
            
        else: 
            msg = (
            "File name: "
            + __file__
            + "\n"
            + "Error line= {}".format(tb.tb_lineno)
            + "\n"
            + "Error: {}".format(sys.exc_info()[0])
            + " "
            + str(e)
        )
            self.error = True
            
        self.writeLog(msg)
        
    def writeLog(self, msg):
        f = open(self.filedirectory + "/" + self.DBname + "/" + self.DBname + "_log.txt", "a")
        msg += "\n\n"
        f.write(msg)
        f.close()
    
    def initialize(self, dbname):
        
        self.createYouTubeDatabase(dbname)
        self.createYouTubeInfoTable(dbname)
        self.createYouTubeReplyTable(dbname)
        self.DBname = dbname
    
    def connect(self):
        try:
            self.conn = pymysql.connect(host='127.0.0.1', user='root', password=self.password, charset='utf8mb4', read_timeout = 2, write_timeout = 2, connect_timeout = 2)    
        except Exception as e:
            self.error_exception(e)
            raise  # 연결 실패시 예외를 다시 발생시켜 호출자에게 알림

    def setDBName(self, name):
        self.dbname = name

    #YouTube DB생성(NaverNews_DB) 함수
    def createYouTubeDatabase(self,dbname):
        try:
            self.dbname = dbname
            self.connect()
            curs = self.conn.cursor() #cursor = 데이터베이스 쿼리를 실행하고 결과를 관리하는 객체, curs변수에 생성
            #NaverNews_DB를 생성하는 쿼리
            query = """CREATE DATABASE """+dbname # 데이터 베이스 생성
            curs.execute(query) # query를 excute
            print('DB를 생성. DB_NAME :' , dbname)
            print("")
            self.conn.commit()    

            # NaverNews_DB의 문자세트를 utf8로 변환
            query = """ALTER DATABASE """+ dbname + """ CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;"""
            curs.execute(query)
            self.conn.commit()
            self.conn.close()

        except Exception as e:
            self.error_exception(e)
        finally:
            if conn:
                conn.close()

    #YouTube 정보 Table 생성 함수
    def createYouTubeInfoTable(self, dbname):
        self.connect()
        curs = self.conn.cursor()
        query = """use """+dbname
        curs.execute(query)
        self.conn.commit()
        #YouTube라는 ID, URL, TITLE 등등을 포함하는 테이블을 생성
        query = """create table youtube_info(   
                                            info_id int not null auto_increment primary key,
                                            channel text,
                                            video_url text,
                                            video_title text,
                                            video_description text,
                                            video_date text,
                                            view_count text,
                                            like_count text,
                                            comment_count text
                                            )"""
        try:
            curs.execute(query)
            self.conn.commit()
            query = """ALTER TABLE youtube_info CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;"""
            curs.execute(query)
            self.conn.commit()
            self.conn.close()
        except Exception as e:
            self.error_exception(e)
        finally:
            if conn:
                conn.close()

    #YouTube 댓글 Table 생성 함수
    def createYouTubeReplyTable(self,dbname):
        self.connect()
        curs = self.conn.cursor()
        query = """use """+dbname
        curs.execute(query)
        self.conn.commit()
        #NaverNews라는 ID, URL, TITLE 등등을 포함하는 테이블을 생성
        query = """create table youtube_replies(   
                                            info_id int not null, 
                                            reply_id int not null auto_increment primary key, 
                                            writer text,
                                            reply_date text,
                                            reply text, 
                                            r_Like text,
                                            rere_count text,
                                            FOREIGN KEY(info_id) REFERENCES youtube_info(info_id) ON UPDATE CASCADE ON DELETE CASCADE
                                            )"""

        try:
            curs.execute(query)
            self.conn.commit()
            query = """ALTER TABLE youtube_replies CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;"""
            curs.execute(query)
            self.conn.commit()
            self.conn.close()
        except Exception as e:
            self.error_exception(e)
        finally:
            if conn:
                conn.close()

    #YouTube 댓글 DB입력
    def insertYouTubeReplyData(self, Info_ID, Reply_ID, Writer, ReplyDate, Reply ,R_Like, ReRe_count):
        try:
            self.connect()
            curs = self.conn.cursor()
            query = """insert into """ +self.dbname+ """.Youtube_Replies(Info_ID, 
                                                    Writer, 
                                                    reply_date, 
                                                    Reply,
                                                    R_Like,
                                                    ReRe_count
                                                    ) values (%s ,%s, %s, %s, %s, %s)"""
            curs.execute(query, (Info_ID, Writer, ReplyDate, Reply, R_Like, ReRe_count))
            self.conn.commit()
            self.conn.close()
            lastIndex = curs.lastrowid
            return lastIndex
        except Exception as e:
            self.error_exception(e)
        finally:
            if conn:
                conn.close()
        

    #YouTube 정보 데이터 추가
    def insertYouTubeInfoData(self, data):
        try:
            self.connect()
            curs = self.conn.cursor()
            lastIndex = -1 
            query = """ insert into """ +self.dbname+ """.youtube_info (
            info_id,
            channel,
            video_url,
            video_title,
            video_description,
            video_date,
            view_count,
            like_count,
            comment_count
            ) select * from ( select %s as a, %s as b, %s as c, %s as d, %s as e, %s as f, %s as g, %s as h, %s as i) as tmp"""
                        
            curs.execute(query, (data['info_id'], 
                                data['channel'], 
                                data['video_url'], 
                                data['video_title'], 
                                data['video_description'], 
                                data['video_date'],
                                data['view_count'],
                                data['like_count'],
                                data['comment_count']
                                ))
            lastIndex = curs.lastrowid
            self.conn.commit()
            self.conn.close()
            
            return lastIndex
        
        except Exception as e:
            self.error_exception(e)
        finally:
            if conn:
                conn.close()
##########################################################################################################   
         
def control():

    print("================ Crawler Controller ================\n")
    print("크롤링 대상\n")
    print("1. 네이버 뉴스\n2. 네이버 블로그\n3. 유튜브\n4. 프로그램 종료")
    
    while True:
        control_ask = int(input("\n입력: "))
        if control_ask in [1,2,3,4]:
            break
        else:
            print("다시 입력하세요")
    
    print("\n====================================================")
    
    crawler = Crawler()
    
    if control_ask == 1:
        crawler.crawl_news()
    
    elif control_ask == 2:
        crawler.crawl_blog()
        
    elif control_ask == 3:
        crawler.crawl_youtube()
    
    else:
        sys.exit()
            
control()
