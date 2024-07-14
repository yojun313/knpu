# -*- coding: utf-8 -*-
import os
import sys

CRAWLERPACKAGE_PATH = os.path.dirname(os.path.abspath(__file__))
CRAWLER_PATH        = os.path.dirname(CRAWLERPACKAGE_PATH)
COLLECTION_PATH     = os.path.join(CRAWLER_PATH, 'Collection')

import socket
import csv
import json


class ToolPackage:
    def __init__(self):
        pass
    # Set folder path depending on the computer
    def pathFinder(self):
        
        if socket.gethostname() == "DESKTOP-502IMU5":
            crawler_folder_path = 'C:/Users/User/Desktop/BIGMACLAB/CRAWLER'
            scrapdata_path      = os.path.join(self.crawler_folder_path, 'scrapdata')
            token_path          = self.crawler_folder_path
            computer_name       = 'HP OMEN'
            
        elif socket.gethostname() == "DESKTOP-0I9OM9K":
            crawler_folder_path = 'C:/Users/User/Desktop/BIGMACLAB/CRAWLER'
            scrapdata_path      = os.path.join(self.crawler_folder_path, 'scrapdata')
            token_path          = self.crawler_folder_path
            computer_name       = 'HP Z8'
        
        elif socket.gethostname() == "Yojuns-MacBook-Pro.local":
            crawler_folder_path = '/Users/yojunsmacbookprp/Documents/BIGMACLAB/CRAWLER'
            scrapdata_path      = os.path.join(self.crawler_folder_path, 'scrapdata')
            token_path          = self.crawler_folder_path
            computer_name       = "Yojun's MacBook Pro"

        
        return {'scrapdata_path' : scrapdata_path, 'token_path' : token_path, 'computer_name' : computer_name}
    
    # For testing Crawler_Package
    def CrawlerChecker(self, target, result_option = False):
            
        if isinstance(target, int) == True:
            print("Error Code:", target)

        elif isinstance(target, dict):
            print("GOOD")
            
        if result_option == True:
            print(target)
    
    def read_txt(self, filepath):
        txt_path = filepath
        result_list = []
        
        with open(txt_path) as f:
            lines = f.readlines()
        for element in lines:
            element = element.replace('\n', '')
            result_list.append(element)
        
        return result_list
    
    # list data를 csv로 저장
    def ListToCSV(self, object_list, csv_path, csv_name):
        with open(os.path.join(csv_path, csv_name), 'w', newline = '', encoding='utf-8-sig') as object:
            csv.writer(object).writerows(object_list)
    
    def get_userEmail(self, name):
        user_list = self.read_txt(os.path.join(COLLECTION_PATH, 'userList.txt'))
        user_dict = {}
        for user in user_list:
            name, email = user.split()
            user_dict[name] = email
        
        try:
            userEmail = user_dict[name]
            
        except:
            userEmail = 'moonyojun@naver.com'
        
        return userEmail
    
    def print_json(self, json_data):
        
        # 파이썬 객체를 보기 쉽게 문자열로 변환 (들여쓰기 포함)
        pretty_json_str = json.dumps(json_data, indent=4, ensure_ascii=False)
        
        print(pretty_json_str)

if __name__ == '__main__':
    ToolPackage_obj = ToolPackage()
    print(ToolPackage_obj.get_userEmail())