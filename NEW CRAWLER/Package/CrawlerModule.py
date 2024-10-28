# -*- coding: utf-8 -*-
import os
import sys

PACKAGE_PATH = os.path.dirname(os.path.abspath(__file__))
CRAWLER_PATH        = os.path.dirname(PACKAGE_PATH)

sys.path.append(PACKAGE_PATH)

from user_agent import generate_navigator
from ToolModule import ToolModule
import random
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import timedelta
import urllib3
import warnings
from bs4 import BeautifulSoup
import traceback
import time
import calendar
from datetime import datetime
import aiohttp
import asyncio
import platform
from rich.console import Console
from rich.live import Live
from rich.table import Table

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# 옵션 유무는 True(yes) 또는 False(no)
class CrawlerModule(ToolModule):
    
    startTime = time.time()

    def __init__(self):
        super().__init__()

        
        self.error_detector_option = False

        self.console = Console()
        self.live = None
        
        self.socketnum = 1
        
        self.mySQL = self.pathFinder()['MYSQL']

        self.PrintData = {
            'currentDate': '',
            'percent'    : '',
            'web_option' : False,
            'api_num'    : 1
        }   
        
        self.IntegratedDB = {
            'UrlCnt'          : 0,
            'TotalArticleCnt' : 0,
            'TotalReplyCnt'   : 0,
            'TotalRereplyCnt' : 0
        }

    def setCrawlSpeed(self, speed):
        self.socketnum = speed

    def error_detector_option_on(self):
        self.error_detector_option = True

    def clear_screen(self):
        if platform.system() == "Windows":
            os.system("cls")
        else:
            os.system("clear")
        
    def setPrintData(self, currentDate, percent, web_option, api_num = 0):
    
        self.PrintData['currentDate'] = currentDate
        self.PrintData['percent']     = percent
        self.PrintData['web_option']  = web_option
        self.PrintData['api_num']     = api_num
    
    def CountReturn(self):
        return self.IntegratedDB

    def error_dump(self, code, msg, target):
        error_data = {
            'Error Code': code,
            'Error Msg': msg,
            'Error Target': target
        }
        return error_data
        
    def random_heador(self):
        navigator = generate_navigator()
        navigator = navigator['user_agent']
        return {"User-Agent": navigator}
 
    def RequesterChecker(self, data):
        if isinstance(data, dict):
            return False
        return True

    
    # 프록시 기반 반복 요청 기능 / self.proxy_option으로 ON/OFF / header, parameter 전달 가능
    def Requester_get(self, url, headers = {}, params = {}, proxies = {}, cookies = {}):
        try:
            if headers == {}:
                headers = self.random_heador()
            
            session = requests.Session()
            retries = Retry(total = 3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
            session.mount('https://', HTTPAdapter(max_retries=retries))
            response = session.get(url, headers = headers, params = params, verify = False)
            
            return response

        except Exception as e:
            return self.error_dump(1001, self.error_detector(), url)

    def Requester_post(self, url, headers = {}, data = {}):
        try:
            if headers == {}:
                headers = self.random_heador()
            
            session = requests.Session()
            retries = Retry(total = 3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
            session.mount('https://', HTTPAdapter(max_retries=retries))
            response = session.post(url, headers = headers, data = data, verify=False)
            
            return response

        except Exception as e:
            return self.error_dump(1001, self.error_detector(), url)


    def error_detector(self):
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
            "\n\n[ ERROR DETECTED! ]\n"
            f"{'Function name:':<20} {function_name}\n"
            f"{'Exception type:':<20} {exc_type.__name__}\n"
            f"{'Exception message:':<20} {exc_value}\n"
            f"{'File name:':<20} {file_name}\n"
            f"{'Line number:':<20} {line_number}\n"
            f"{'Traceback:':<19}{formatted_traceback}"
        )
        
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
    
    print("hello")