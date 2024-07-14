import socket
import csv
import json
import os

class ToolPackage:
    def __init__(self):
        pass
    
    # Set folder path depending on the computer
    def pathFinder(self):
        if socket.gethostname() == "Yojuns-MacBook-Pro.local":
            scrapdata_path = "/Users/yojunsmacbookprp/Documents/BIGMACLAB/CRAWLER/scrapdata"
        
        return {'scrapdata_path' : scrapdata_path}
    
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
    
    def print_json(self, json_data):
        
        # 파이썬 객체를 보기 쉽게 문자열로 변환 (들여쓰기 포함)
        pretty_json_str = json.dumps(json_data, indent=4, ensure_ascii=False)
        
        print(pretty_json_str)