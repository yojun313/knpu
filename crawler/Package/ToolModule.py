# -*- coding: utf-8 -*-##
import os
import sys

CRAWLERPACKAGE_PATH = os.path.dirname(os.path.abspath(__file__))
sys.path.append(CRAWLERPACKAGE_PATH)

import socket
import csv
import json
import chardet
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

DB_IP = '121.152.225.232'
LOCAL_IP = '192.168.0.3'

SSH_HOST = os.getenv("SSH_HOST")
SSH_PORT = int(os.getenv("SSH_PORT", 22))
SSH_USER = os.getenv("SSH_USER")
SSH_KEY = os.getenv("SSH_KEY")

# MongoDB 설정
MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
MONGO_PORT = int(os.getenv("MONGO_PORT", 27017))
MONGO_USER = os.getenv("MONGO_USER")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD")
MONGO_AUTH_DB = os.getenv("MONGO_AUTH_DB", "admin")


class ToolModule:
    def __init__(self):
        pass
    # Set folder path depending on the computer
    def pathFinder(self):
        if socket.gethostname() == "Yojuns-MacBook-Pro.local":
            computer_name       = "Yojun's MacBook Pro"
        
        elif socket.gethostname() == "knpu":
            computer_name = "Server"
            
        elif socket.gethostname() == "BigMacServer":
            computer_name = "BIGMACLAB SERVER"

        returnData = {
            'crawler_folder_path': os.getenv('DATA_PATH'), 
            'scrapdata_path' : os.getenv('CRAWLDATA_PATH'),
            'token_path' : os.getenv('DATA_PATH'), 
            'computer_name' : computer_name, 
        }
        return returnData
    
    def mongoDB(self):
        hostname = socket.gethostname()
        is_server = ("knpu" in hostname or "server" in hostname)  # 서버 이름 기준으로 판단

        if is_server:
            # 서버 내부에서 실행 → 로컬 MongoDB 바로 사용
            self.mongoClient = MongoClient(
                f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}"
                f"@localhost:{MONGO_PORT}/?authSource={MONGO_AUTH_DB}"
            )
        else:
            import warnings
            warnings.filterwarnings("ignore", module="paramiko")
            from sshtunnel import SSHTunnelForwarder
            # 외부에서 실행 → SSH 터널 사용
            server = SSHTunnelForwarder(
                (SSH_HOST, SSH_PORT),
                ssh_username=SSH_USER,
                ssh_pkey=SSH_KEY,
                remote_bind_address=(MONGO_HOST, MONGO_PORT)
            )
            server.start()

            self.mongoClient = MongoClient(
                f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}"
                f"@127.0.0.1:{server.local_bind_port}/?authSource={MONGO_AUTH_DB}"
            )
    
    def read_txt(self, filepath):
        txt_path = filepath
        result_list = []

        # 파일을 바이너리 모드로 열어 raw 데이터 읽기
        with open(txt_path, 'rb') as file:
            raw_data = file.read()
            result = chardet.detect(raw_data)
            charenc = result['encoding']

        # 감지된 인코딩을 사용하여 파일을 텍스트 모드로 읽기
        with open(txt_path, 'r', encoding=charenc) as f:
            lines = f.readlines()
        
        for element in lines:
            element = element.replace('\n', '')
            result_list.append(element)
        
        return result_list
    
    # list data를 csv로 저장
    def ListToCSV(self, object_list, csv_path, csv_name):
        with open(os.path.join(csv_path, csv_name), 'w', newline = '', encoding='utf-8-sig', errors='ignore') as object:
            csv.writer(object).writerows(object_list)
    
    def get_userInfo(self, input_name):
        self.mongoDB()
        db = self.mongoClient['manager']['users']
        user = db.find_one({'name': input_name})
        if user is None:
            return False
        return {'Email': user['email'], 'PushOver': user['pushoverKey']}

    def sendPushOver(self, msg, user_key):
        app_key_list  = ["a273soeggkmq1eafdyghexusve42bq", "a39cudwdti3ap97kax9pmvp6gdm2b9"]

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

    def print_json(self, json_data):
        
        # 파이썬 객체를 보기 쉽게 문자열로 변환 (들여쓰기 포함)
        pretty_json_str = json.dumps(json_data, indent=4, ensure_ascii=False)
        
        print(pretty_json_str)

    def error_extractor(self, errorCode):
        error_dic = {
            1001: '[Internal Error] CrawlerPackage -> Requester: Internal unexpected error',
            1002: '[Internal Error] CRAWLER.py : Internal unexpected error',
            1003: '[Internal Error] CrawlerPackage -> asyncRequester: Internal unexpected error',
            2001: '[Parameter Error] NaverNewsCrawler -> urlCollector: Keyword type error',
            2002: '[Parameter Error] NaverNewsCrawler -> urlCollector: DateForm error',
            2003: '[Internal Error] NaverNewsCrawler -> urlCollector: Internal unexpected error',
            2004: '[Parameter Error] NaverNewsCrawler -> articleCollector: newsURL type/form error',
            2005: '[Internal Error] NaverNewsCrawler -> articleCollector: Internal unexpected error',
            2006: '[Parameter Error] NaverNewsCrawler -> replyCollector: newsURL type/form error',
            2007: '[Internal Error] NaverNewsCrawler -> replyCollector: Internal unexpected error',
            2008: '[Parameter Error] NaverNewsCrawler -> rereplyCollector: newsURL type/form error',
            2009: '[Parameter Error] NaverNewsCrawler -> rereplyCollector: list type error',
            2010: '[Internal Error] NaverNewsCrawler -> rereplyCollector: Internal unexpected error',
            2011: '[Parameter Error] NaverBlogCrawler -> urlCollector: Keyword type error',
            2012: '[Parameter Error] NaverBlogCrawler -> urlCollector: DateForm error',
            2013: '[Internal Error] NaverBlogCrawler -> urlCollector: Internal unexpected error', 
            2014: '[Parameter Error] NaverBlogCrawler -> articleCollector: blogURL type/form error',
            2015: '[Internal Error] NaverBlogCrawler -> articleCollector: Internal unexpected error',
            2016: '[Parameter Error] NaverBlogCrawler -> replyCollector: blogURL type/form error',
            2017: '[Internal Error] NaverBlogCrawler -> replyCollector: Internal unexpected error',
            2018: '[Parameter Error] NaverCafeCrawler -> urlCollector: Keyword type error',
            2019: '[Parameter Error] NaverCafeCrawler -> urlCollector: DateForm error',
            2020: '[Internal Error] NaverCafeCrawler -> urlCollector: Internal unexpected error',
            2021: '[Parameter Error] NaverCafeCrawler -> articleCollector: cafeURL type/form error',
            2022: '[Internal Error] NaverCafeCrawler -> articleCollector: Internal unexpected error',
            2023: '[Parameter Error] NaverCafeCrawler -> replyCollector: cafeURL type/form error',
            2024: '[Internal Error] NaverCafeCrawler -> replyCollector: Internal unexpected error',
            2025: '[Parameter Error] YouTubeCrawler -> urlCollector: URL type/form error',
            2026: '[Internal Error] YouTubeCrawler -> urlCollector: Internal unexpected error',
            2027: '[Parameter Error] YouTubeCrawler -> replyCollector: URL type/form error',
            2028: '[Internal Error] YouTubeCrawler -> replyCollector: Internal unexpected error',
            2029: '[Parameter Error] ChinaDailyCrawler -> articleCollector: Keyword type error',
            2030: '[Parameter Error] ChinaDailyCrawler -> articleCollector: DateForm error',
            2031: '[Internal Error] ChinaDailyCrawler -> articleCollector: Internal unexpected error',
            2032: '[Parameter Error] ChinaSinaCrawler -> urlCollector: Keyword type error',
            2033: '[Parameter Error] ChinaSinaCrawler -> urlCollector: DateForm error',
            2034: '[Internal Error] ChinaSinaCrawler -> urlCollector: Internal unexpected error',
            2035: '[Parameter Error] ChinaSinaCrawler -> articleCollector: URL type/form error',
            2036: '[Internal Error] ChinaSinaCrawler -> articleCollector: Internal unexpected error',
            2037: '[Parameter Error] ChinaSinaCrawler -> replyCollector: URL type/form error',
            2038: '[Internal Error] ChinaSinaCrawler -> replyCollector: Internal unexpected error',
            2039: '[Internal Error] YouTubeCrawler -> urlCollector: Internal unexpected error'
        }
        return error_dic[errorCode]

if __name__ == '__main__':
    ToolModule = ToolModule()
