# -*- coding: utf-8 -*-
import os

CRAWLERPACKAGE_PATH = os.path.dirname(os.path.abspath(__file__))
CRAWLER_PATH        = os.path.dirname(CRAWLERPACKAGE_PATH)
COLLECTION_PATH     = os.path.join(CRAWLER_PATH, 'Collection')

import socket
import csv
import json
import chardet

class ToolModule:
    def __init__(self):
        pass
    # Set folder path depending on the computer
    def pathFinder(self):
        
        if socket.gethostname() == "DESKTOP-502IMU5":
            crawler_folder_path = 'C:/Users/User/Desktop/BIGMACLAB/CRAWLER'
            scrapdata_path      = os.path.join(crawler_folder_path, 'scrapdata')
            token_path          = crawler_folder_path
            computer_name       = 'HP OMEN'
            
        elif socket.gethostname() == "DESKTOP-0I9OM9K":
            crawler_folder_path = 'C:/Users/User/Desktop/BIGMACLAB/CRAWLER'
            scrapdata_path      = os.path.join(crawler_folder_path, 'scrapdata')
            token_path          = crawler_folder_path
            computer_name       = 'HP Z8'
        
        elif socket.gethostname() == "Yojuns-MacBook-Pro.local":
            crawler_folder_path = '/Users/yojunsmacbookprp/Documents/BIGMACLAB/CRAWLER'
            scrapdata_path      = os.path.join(crawler_folder_path, 'scrapdata')
            token_path          = crawler_folder_path
            computer_name       = "Yojun's MacBook Pro"

        
        return {'scrapdata_path' : scrapdata_path, 'token_path' : token_path, 'computer_name' : computer_name}
    # For testing Crawler_Package
    def CrawlerChecker(self, target, result_option = False):
            
        if isinstance(target, dict):
            first_key = list(target.keys())[0]
            if first_key == 'Error Code':
                print(target['Error Code'])
                return
            else:
                print("GOOD\n")
        if result_option == True:
            print(target)
    
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
        with open(os.path.join(csv_path, csv_name), 'w', newline = '', encoding='utf-8-sig') as object:
            csv.writer(object).writerows(object_list)
    
    def get_userEmail(self, input_name):
        user_list = self.read_txt(os.path.join(COLLECTION_PATH, 'userList.txt'))
        user_dict = {}
        for user in user_list:
            name, email = user.split()
            user_dict[name] = email
        try:
            userEmail = user_dict[input_name]
        except:
            userEmail = 'moonyojun@naver.com'
        
        return userEmail
    
    def print_json(self, json_data):
        
        # 파이썬 객체를 보기 쉽게 문자열로 변환 (들여쓰기 포함)
        pretty_json_str = json.dumps(json_data, indent=4, ensure_ascii=False)
        
        print(pretty_json_str)

    def error_extractor(self, errorCode):
        error_dic = {
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
            2038: '[Internal Error] ChinaSinaCrawler -> replyCollector: Internal unexpected error'
        }
        return error_dic[errorCode]

if __name__ == '__main__':
    ToolPackage_obj = ToolModule()
    print(ToolPackage_obj.get_userEmail('문요준'))