# -*- coding: utf-8 -*-
import os
import sys

CRAWLERPACKAGE_PATH = os.path.dirname(os.path.abspath(__file__))
CRAWLER_PATH        = os.path.dirname(CRAWLERPACKAGE_PATH)
BIGMACLAB_PATH      = os.path.dirname(CRAWLER_PATH)
MANAGER_PATH          = os.path.join(BIGMACLAB_PATH, 'MANAGER')

sys.path.append(MANAGER_PATH)

import socket
import csv
import json
import chardet
import requests
from mySQL import mySQL

class ToolModule:
    def __init__(self):
        pass
    # Set folder path depending on the computer
    def pathFinder(self, name = ''):

        if socket.gethostname() == "Yojuns-MacBook-Pro.local":
            crawler_folder_path = '/Users/yojunsmacbookprp/Documents/BIGMACLAB/CRAWLER'
            scrapdata_path      = os.path.join(crawler_folder_path, 'scrapdata')
            token_path          = crawler_folder_path
            computer_name       = "Yojun's MacBook Pro"
            RealTimeCrawler_DBPath = os.path.join(crawler_folder_path, 'RealTimeCrawler_DB')
            mySQL_obj = mySQL(host='192.168.0.15', user='root', password='kingsman', port=3306)
               
        elif socket.gethostname() == "DESKTOP-502IMU5":
            crawler_folder_path = 'C:/BIGMACLAB/CRAWLER'
            scrapdata_path      = os.path.join(crawler_folder_path, 'scrapdata', f'{name}_scrapdata')
            token_path          = crawler_folder_path
            computer_name       = 'HP OMEN'
            RealTimeCrawler_DBPath = os.path.join(crawler_folder_path, 'RealTimeCrawler_DB')
            mySQL_obj = mySQL(host='192.168.0.15', user='admin', password='bigmaclab2022!', port=3306)

        elif socket.gethostname() == "DESKTOP-0I9OM9K":
            crawler_folder_path = 'D:/BIGMACLAB/CRAWLER'
            scrapdata_path      = os.path.join(crawler_folder_path, 'scrapdata', f'{name}_scrapdata')
            token_path          = crawler_folder_path
            computer_name       = 'HP Z8'
            RealTimeCrawler_DBPath = os.path.join(crawler_folder_path, 'RealTimeCrawler_DB')
            mySQL_obj = mySQL(host='192.168.0.15', user='admin', password='bigmaclab2022!', port=3306)
        
        elif socket.gethostname() == "BigMacServer":
            crawler_folder_path = "D:/BIGMACLAB/CRAWLER"
            scrapdata_path = os.path.join(crawler_folder_path, 'scrapdata', f'{name}_scrapdata')
            token_path = crawler_folder_path
            computer_name = "BIGMACLAB SERVER"
            RealTimeCrawler_DBPath = os.path.join(crawler_folder_path, 'RealTimeCrawler_DB')
            mySQL_obj = mySQL(host='localhost', user='root', password='bigmaclab2022!', port=3306)

        returnData = {
            'crawler_folder_path': crawler_folder_path, 
            'scrapdata_path' : scrapdata_path, 
            'token_path' : token_path, 
            'computer_name' : computer_name, 
            'RealTimeCrawler_DBPath' : RealTimeCrawler_DBPath, 
            'MYSQL': mySQL_obj
        }
        return returnData
    
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
    
    def get_userInfo(self, input_name, mysql):
        mysql.connectDB(database_name='user_db')
        df = mysql.TableToDataframe(tableName='user_info')

        email = df.loc[df['Name'] == input_name, 'Email'].values[0]
        pushover = df.loc[df['Name'] == input_name, 'PushOver'].values[0]

        return {'Email': email, 'PushOver': pushover}

    def send_pushOver(self, msg, user_key):
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
    mySQL_obj = mySQL(host='121.152.225.232', user='admin', password='bigmaclab2022!', port=3306, database='User_DB')
