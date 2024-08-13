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

    def __init__(self, proxy_option = False):
        super().__init__()

        self.proxy_option   = proxy_option
        self.error_detector_option = False

        self.console = Console()
        self.live = None
        
        self.socketnum = 1

        if proxy_option == True:
            proxy_path = os.path.dirname(PACKAGE_PATH)
            self.proxy_list = self.read_txt(os.path.join(proxy_path, '아이피샵(유동프록시).txt'))       # 로컬 proxy.txt 파일 경로
        
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

    def printStatus(self, type, option = 1, printData = {}, finish = False):

        WHITE = "\033[37m"
        YELLOW = "\033[33m"
        CYAN = "\033[36m"
        RESET = "\033[0m"

        type_dic = {
            'NaverNews': '기사',
            'NaverBlog': '블로그',
            'NaverCafe': '카페',
            'YouTube': '영상',
            'ChinaDaily': '기사',
            'ChinaSina': '기사'
        }
        type_word = type_dic[type]

        def get_color(option):

            colors = {
                1: {"date": CYAN, "url": YELLOW, "type": YELLOW, "reply": YELLOW, "re_reply": YELLOW},
                2: {"date": YELLOW, "url": CYAN, "type": YELLOW, "reply": YELLOW, "re_reply": YELLOW},
                3: {"date": YELLOW, "url": YELLOW, "type": CYAN, "reply": YELLOW, "re_reply": YELLOW},
                4: {"date": YELLOW, "url": YELLOW, "type": YELLOW, "reply": CYAN, "re_reply": YELLOW},
                5: {"date": YELLOW, "url": YELLOW, "type": YELLOW, "reply": YELLOW, "re_reply": CYAN},
                6: {"date": YELLOW, "url": YELLOW, "type": YELLOW, "reply": CYAN, "re_reply": CYAN}
            }
            return colors.get(option,
                              {"date": YELLOW, "url": YELLOW, "type": YELLOW, "reply": YELLOW, "re_reply": YELLOW})
        color = get_color(option)

        progress_time = time.time()
        loading_second = progress_time - CrawlerModule.startTime
        loadingtime = f"{int(loading_second // 3600):02}:{int(loading_second % 3600 // 60):02}:{int(loading_second % 3600 % 60):02}"

        if self.PrintData['web_option'] == True:
            try:
                if self.PrintData['web_option'] == False:
                    out_str = (
                        f"\r{WHITE}|| 진행: {YELLOW}{printData['percent']}%{WHITE} "
                        f"| 경과: {YELLOW}{loadingtime}{WHITE} "
                        f"| 날짜: {color['date']}{printData['currentDate']}{WHITE} "
                        f"| URL: {color['url']}{self.IntegratedDB['UrlCnt']}{WHITE} "
                        f"| {type_word}: {color['type']}{self.IntegratedDB['TotalArticleCnt']}{WHITE} "
                        f"| 댓글: {color['reply']}{self.IntegratedDB['TotalReplyCnt']}{WHITE} "
                        f"| 대댓글: {color['re_reply']}{self.IntegratedDB['TotalRereplyCnt']}{WHITE} ||{RESET}"
                    )

                else:
                    out_str = (
                        f"\r|| 진행: {printData['percent']}% "
                        f"| 경과: {loadingtime} "
                        f"| 날짜: {printData['currentDate']} "
                        f"| URL: {self.IntegratedDB['UrlCnt']} "
                        f"| {type_word}: {self.IntegratedDB['TotalArticleCnt']} "
                        f"| 댓글: {self.IntegratedDB['TotalReplyCnt']} "
                        f"| 대댓글: {self.IntegratedDB['TotalRereplyCnt']} ||"
                    )

                if type == 'YouTube':
                    if self.PrintData['web_option'] == False:
                        out_str += f" | API num : {YELLOW}{self.PrintData['api_num']} {WHITE}|"
                    else:
                        out_str += f" | API num : {self.PrintData['api_num']} |"

                print(out_str, end = '')
            except:
                pass
        else:
            def generate_table():
                table = Table()

                table.add_column("Target", style="bold yellow")
                table.add_column("Count", style="bold white")

                table.add_row("진행", str(printData['percent'])+'%')
                table.add_row("경과", str(loadingtime))
                table.add_row("날짜", str(printData['currentDate']))
                table.add_row("URL", str(self.IntegratedDB['UrlCnt']))
                table.add_row(f"{type_word}", str(self.IntegratedDB['TotalArticleCnt']))
                table.add_row("댓글", str(self.IntegratedDB['TotalReplyCnt']))
                table.add_row("대댓글", str(self.IntegratedDB['TotalRereplyCnt']))
                if type == 'YouTube':
                    table.add_row("API NUM", str(self.PrintData['api_num']))

                return table

            if self.live is None:
                self.live = Live(console=self.console, refresh_per_second=10)
                self.live.start()

            table = generate_table()

            if self.live is not None:
                self.live.update(table)

            if finish == True:
                self.live.stop()
                self.live = None

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
 
    def random_proxy(self):
        proxy_server = random.choice(self.proxy_list)
        if self.proxy_option == True:
            return {"http": 'http://' + proxy_server, 'https': 'http://' + proxy_server}
        else:
            return None

    def RequesterChecker(self, data):
        if isinstance(data, dict):
            return False
        return True

    
    # 프록시 기반 반복 요청 기능 / self.proxy_option으로 ON/OFF / header, parameter 전달 가능
    def Requester(self, url, headers = {}, params = {}, proxies = {}, cookies = {}):
        try:
            if headers == {}:
                headers = self.random_heador()

            if self.proxy_option == True:
                trynum = 0
                while True:
                    proxies = self.random_proxy()
                    try:
                        main_page = requests.get(url, proxies = proxies, headers = headers, params = params, cookies = cookies, verify = False, timeout = 3)
                        return main_page
                    except Exception as e:
                        if trynum >= 100:
                            return self.error_dump(1001, self.error_detector(), url)
                        trynum += 1
            else:
                return requests.get(url, headers = headers, params = params, verify = False)

        except Exception as e:
            return self.error_dump(1001, self.error_detector(), url)

    # Async Part
    def async_proxy(self):
        proxy_server = random.choice(self.proxy_list)
        if self.proxy_option == True:
            return 'http://' + str(proxy_server)
        else:
            return None
    async def asyncRequester(self, url, headers={}, params={}, proxies='', cookies={}, session=None):
        timeout = aiohttp.ClientTimeout(total=300)
        trynum = 0
        while True:
            try:
                if self.proxy_option:
                    proxies = self.async_proxy()
                async with session.get(url, headers=headers, params=params, proxy=proxies, cookies=cookies, ssl=False, timeout=timeout) as response:
                    return await response.text()
            except (aiohttp.ClientError, asyncio.TimeoutError, Exception) as e:
                if trynum >= 100:
                    return self.error_dump(1003, self.error_detector(), url)
                trynum += 1

    def error_detector(self, error_print_option = False):
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
        
        # Printing the error message to the console
        if error_print_option == True:
            print(error_message)
        return error_message
    
    # 중국 크롤러 용, 전체 기간을 한 달 단위로 쪼갬
    def DateSplitter(self, start_date, end_date):
        # 날짜 문자열을 datetime 객체로 변환
        start = datetime.strptime(str(start_date), '%Y%m%d')
        end = datetime.strptime(str(end_date), '%Y%m%d')
        
        result = []
        current = start

        while current <= end:
            # 현재 날짜의 월의 마지막 날 계산
            _, last_day = calendar.monthrange(current.year, current.month)
            month_end = datetime(current.year, current.month, last_day)
            
            # 월의 마지막 날이 종료 날짜보다 크면 종료 날짜로 설정
            if month_end > end:
                month_end = end
            
            # 월의 시작일과 종료일 추가
            result.append([str(current.strftime('%Y%m%d')), str(month_end.strftime('%Y%m%d'))])
            
            # 다음 달의 첫 번째 날로 이동
            current = month_end + timedelta(days=1)
            current = current.replace(day=1)
        
        return result
    
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