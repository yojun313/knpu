# -*- coding: utf-8 -*-
import sys
import os

CRAWLERPACKAGE_PATH = os.path.dirname(os.path.abspath(__file__))
CRAWLER_PATH        = os.path.dirname(CRAWLERPACKAGE_PATH)
COLLECTION_PATH     = os.path.join(CRAWLER_PATH, 'Collection')

import socket
from user_agent import generate_user_agent, generate_navigator
from ToolPackage import ToolPackage
import random
import requests
import csv
from datetime import datetime, timezone
import urllib3
import warnings
from bs4 import BeautifulSoup
import pandas as pd
import traceback

from urllib.parse import urlparse, parse_qs
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# 옵션 유무는 True(yes) 또는 False(no)
class CrawlerPackage(ToolPackage):
    
    def __init__(self, proxy_option = False):
        
        self.proxy_option   = proxy_option
        self.collection_path = COLLECTION_PATH
        if proxy_option == True:
            self.proxy_list     = self.read_txt(self.collection_path + '/proxy.txt')       # 로컬 proxy.txt 파일 경로

    def random_heador(self):
        navigator = generate_navigator()
        navigator = navigator['user_agent']
        return {"User-Agent": navigator}
 
    def random_proxy(self):
        proxy_server = random.choice(self.proxy_list)
        if self.proxy_option == True:
            return {"http": 'http://' + proxy_server, 'https': 'http://' + proxy_server}
        else:
            return None
    
    # 프록시 기반 반복 요청 기능 / self.proxy_option으로 ON/OFF / header, parameter 전달 가능
    def Requester(self, url, headers = {}, params = {}, proxies = {}, cookies = {}):
        try:
            if headers == {}:
                headers = self.random_heador()
                
            # 프록시를 별도로 지정해서 줬을 때 (네이버 카페 url 수집 전용)
            if proxies != {}:
                trynum = 0
                while True:
                    if trynum >= 3:
                        return 0
                    try:
                        main_page = requests.get(url, proxies = proxies, verify = False, timeout = 3)
                        break
                    except requests.exceptions.Timeout as e:
                        pass
                    except Exception as e:
                        pass
                    trynum += 1
            
                return main_page  
                
            if self.proxy_option == True:
                trynum = 0
                while True:
                    if trynum >= 100000:
                        print("Proxy Error: Check Proxy & Requester... Program Shut Down")
                        sys.exit()
                    
                    proxies = self.random_proxy()
                    try:
                        main_page = requests.get(url, proxies = proxies, headers = headers, params = params, cookies = cookies, verify = False, timeout = 3)
                        break
                    except requests.exceptions.Timeout as e:
                        pass
                    except Exception as e:
                        pass
                    trynum += 1
            
                return main_page  
            else:
                return requests.get(url, headers = headers, params = params, verify = False)
        
        except Exception:
            print("Critical Error: Check Proxy & Requester... Program Shut Down")
            sys.exit()
        
    def error_detector(self, error_print_option):
        exc_type, exc_value, exc_traceback = sys.exc_info()
    
        # Formatting the traceback
        formatted_traceback = ''.join(traceback.format_tb(exc_traceback))
        
        # Extracting the last traceback entry
        last_traceback = traceback.extract_tb(exc_traceback)[-1]
        file_name = last_traceback.filename
        line_number = last_traceback.lineno
        function_name = last_traceback.name
        
        # Creating the detailed error message
        error_message = (
            "\n[ ERROR DETECTED! ]\n"
            f"{'Function name:':<20} {function_name}\n"
            f"{'Exception type:':<20} {exc_type.__name__}\n"
            f"{'Exception message:':<20} {exc_value}\n"
            f"{'File name:':<20} {file_name}\n"
            f"{'Line number:':<20} {line_number}\n"
            f"{'Traceback:':<19}{formatted_traceback}"
        )
        
        # Printing the error message to the console
        if error_print_option == True:
            print(error_message)
        return error_message
        
    def urlCollector(self, keyword, startDate, endDate, site, urlLimiter = []):
        startDate = datetime.strptime(str(startDate), "%Y%m%d").strftime("%-m/%-d/%Y")
        endDate   = datetime.strptime(str(endDate), "%Y%m%d").strftime("%-m/%-d/%Y")
        currentPage = 0
        
        urlList = []
        
        try:
            while True:
                
                search_page_url = 'https://www.google.co.kr/search?q={}+site:{}&hl=ko&source=lnt&tbs=cdr%3A1%2Ccd_min%3A{}%2Ccd_max%3A{}&tbm=&start={}'.format(keyword, site, startDate, endDate, currentPage)
                header = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                cookie = {'CONSENT' : 'YES'}
                
                main_page = self.Requester(search_page_url, headers = header, cookies = cookie)
                main_page = BeautifulSoup(main_page.text, "lxml")
                site_result = main_page.select("a[jsname = 'UWckNb']")
                
                if site_result == []:
                    break
                
                for a in site_result:
                    add_link = a['href']
                    
                    if add_link not in urlList:
                        # Check if the URL contains any characters from urlLimiter
                        contains_limiter = False
                        for char in urlLimiter:
                            if char in add_link:
                                contains_limiter = True
                                break
                        
                    if contains_limiter == False:
                        urlList.append(add_link)
                    
                currentPage += 10
            
            urlList = list(set(urlList))
            returnData = {
                'urlList' : urlList,
                'urlCnt'  : len(urlList)
            }
            
            return returnData
        
        except Exception as e:
            self.error_detector()
                
    def articleCollector(self):
        pass
    
    def replyCollector(self):
        pass


if __name__ == "__main__":
    
    CrawlerPackage_obj = CrawlerPackage(True)
    urlList = CrawlerPackage_obj.urlCollector("급발진", 20240601, 20240630, site='youtube.com', urlLimiter=['playlist', 'shorts', 'channel', 'user', 'm.'])

    for url in urlList:
        print(url)