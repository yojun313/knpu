# -*- coding: utf-8 -*-
import os
import sys

DCinsideCRAWLERPACKAGE_PATH = os.path.dirname(os.path.abspath(__file__))
PACKAGE_PATH      = os.path.dirname(DCinsideCRAWLERPACKAGE_PATH)
sys.path.append(PACKAGE_PATH)

import time
from datetime import datetime, timedelta
from CrawlerModule import CrawlerModule
import json
import re
import warnings
from datetime import datetime
import pandas as pd
import urllib3
from bs4 import BeautifulSoup
from user_agent import generate_navigator
import asyncio
import aiohttp
import urllib.parse
import html
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

class DCinsideCrawler(CrawlerModule):
    
    def __init__(self, print_status_option=False):
        super().__init__()
        self.print_status_option = print_status_option

    def _format_date(self, date_str):
        date_obj = datetime.strptime(date_str, "%Y%m%d")
        formatted_date = f"{date_obj.month}/{date_obj.day}/{date_obj.year}"
        return formatted_date
    
    def urlCollector(self, keyword, startDate, endDate, checkPage, previous_urls, speed):
        site = 'dcinside.com'
        startDate = self._format_date(startDate)
        endDate = self._format_date(endDate)
        currentPage = 0

        urlList = []

        try:
            if self.print_status_option == True:
                self.IntegratedDB['UrlCnt'] = 0
                #self.printStatus('YouTube', 1, self.PrintData)
                
            
            search_page_url = 'https://www.google.co.kr/search?q={}+site:{}&hl=ko&source=lnt&tbs=cdr%3A1%2Ccd_min%3A{}%2Ccd_max%3A{}&start={}'.format(
                keyword, site, startDate, endDate, currentPage)
            header = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            cookie = {'CONSENT': 'YES'} 

            main_page = self.Requester_get(search_page_url, headers=header, cookies=cookie)
            time.sleep(speed)
            if self.RequesterChecker(main_page) == False:
                return main_page
            main_page = BeautifulSoup(main_page.text, "lxml")
            site_result = main_page.select("a[jsname = 'UWckNb']")
            
            for a in site_result:
                add_link = a['href']

                if add_link not in urlList and ('https://m.dcinside.com/' in add_link or 'https://gall.dcinside.com/' in add_link):                     
                    urlList.append(add_link)
                    self.IntegratedDB['UrlCnt'] += 1
                    
            if self.print_status_option == True:
                "printStatus"
                #self.printStatus('YouTube', option=2, printData=self.PrintData)
            currentPage += 10

            if checkPage >=2:
                for i in range(checkPage-1):
                    if self.lastpage == True:
                        break
                    search_page_url = 'https://www.google.co.kr/search?q={}+site:{}&hl=ko&source=lnt&tbs=cdr%3A1%2Ccd_min%3A{}%2Ccd_max%3A{}&start={}'.format(
                    keyword, site, startDate, endDate, currentPage)
                    header = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                    cookie = {'CONSENT': 'YES'} 

                    main_page = self.Requester_get(search_page_url, headers=header, cookies=cookie)
                    time.sleep(speed)
                    if self.RequesterChecker(main_page) == False:
                        return main_page
                    main_page = BeautifulSoup(main_page.text, "lxml")
                    site_result = main_page.select("a[jsname = 'UWckNb']")
                    if site_result == []:
                        break
                    for a in site_result:
                        add_link = a['href']

                        if add_link not in urlList and ('https://m.dcinside.com/' in add_link or 'https://gall.dcinside.com/' in add_link):                     
                            urlList.append(add_link)
                            self.IntegratedDB['UrlCnt'] += 1
                    
                    for a in site_result:
                        add_link = a['href']
                        if add_link in previous_urls:
                            self.lastpage = True
                            break
                        
                    currentPage += 10
                        
            elif checkPage == 1:
                pass
            
            elif checkPage == 0:
                for url in urlList:
                    if url in previous_urls:
                        self.lastpage = True
                        break
                    
                while not self.lastpage:
                    search_page_url = 'https://www.google.co.kr/search?q={}+site:{}&hl=ko&source=lnt&tbs=cdr%3A1%2Ccd_min%3A{}%2Ccd_max%3A{}&start={}'.format(
                        keyword, site, startDate, endDate, currentPage)
                    header = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                    cookie = {'CONSENT': 'YES'} 

                    main_page = self.Requester_get(search_page_url, headers=header, cookies=cookie)
                    time.sleep(speed)
                    if self.RequesterChecker(main_page) == False:
                        return main_page
                    main_page = BeautifulSoup(main_page.text, "lxml")
                    site_result = main_page.select("a[jsname = 'UWckNb']")
                    if site_result == []:
                        break

                    for a in site_result:
                        add_link = a['href']

                        if add_link not in urlList and ('https://m.dcinside.com/' in add_link or 'https://gall.dcinside.com/' in add_link):                        
                            urlList.append(add_link)
                            self.IntegratedDB['UrlCnt'] += 1
                            
                    if self.print_status_option == True:
                        "printStatus"
                        #self.printStatus('YouTube', option=2, printData=self.PrintData)
                    currentPage += 10
                    
                    for a in site_result:
                        add_link = a['href']
                        if add_link in previous_urls:
                            self.lastpage = True
                            break
            
            returnData = {
                'urlList': urlList,
                'urlCnt': len(urlList)
            }
            # return part
            return returnData

        except Exception as e:
            self.error_detector()
    
    def RTurlCollector(self, keyword, checkPage, previous_urls, speed):     # 파라미터로 (검색어, 페이지 수) 전달
        try:
            if isinstance(keyword, str) == False:
                return self.error_dump(2000, 'Check Keyword', keyword)
        except:
            return self.error_dump(2001, 'Check DateForm')
        
        try:
            if self.print_status_option == True:
                self.IntegratedDB['UrlCnt'] = 0
                "printStatus"
                #self.printStatus('NaverNews', 1, self.PrintData)

            urlList = []
            self.lastpage = False
            keyword = keyword.replace('&', '.26').replace('+', '.2B').replace('"', '.22').replace('|', '.7C').replace(' ', '.20')
            api_url = "https://search.dcinside.com/post/"
            response = self.Requester_get(api_url+"p/1/q/"+keyword)
            time.sleep(speed)
            if self.RequesterChecker(response) == False:
                return response
            soup = BeautifulSoup(response.content, 'html.parser')
            elements = soup.select('#container > div > section:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(2) > ul > li > a')
            pre_urlList = [element['href'] for element in elements]
            self.IntegratedDB['UrlCnt'] += len(pre_urlList)

            if self.print_status_option == True:
                "printStatus"
                #self.printStatus('NaverNews', 2, self.PrintData)
            
            if not pre_urlList:
                return self.urlCollector(keyword=keyword, startDate=time.strftime("%Y%m%d"), endDate= (datetime.now() - timedelta(days=1)).strftime("%Y%m%d"),checkPage= checkPage, previous_urls=previous_urls, speed=speed)
            
            urlList.extend(pre_urlList)
            
            if checkPage >=2:
                for i in range(checkPage-1):
                    if self.lastpage == True:
                        break
                    nextUrl = api_url+"p/"+str(i+2)+"/q/"+keyword
                    response = self.Requester_get(nextUrl)
                    time.sleep(speed)
                    if self.RequesterChecker(response) == False:
                        return response
                    soup = BeautifulSoup(response.content, 'html.parser')
                    elements = soup.select('#container > div > section:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(2) > ul > li > a')
                    pre_urlList = [element['href'] for element in elements]
                    self.IntegratedDB['UrlCnt'] += len(pre_urlList)
                    for url in pre_urlList:
                        urlList.append(url)
                    
                    for url in pre_urlList:
                        if url in previous_urls:
                            self.lastpage = True
                            break
                        
            elif checkPage == 1:
                pass
            
            elif checkPage == 0:
                for url in pre_urlList:
                    if url in previous_urls:
                        self.lastpage = True
                        break
                    
                page = 1
                while self.lastpage == False:
                    page = page + 1
                    nextUrl = api_url+"p/"+str(page)+"/q/"+keyword
                    response = self.Requester_get(nextUrl)
                    time.sleep(speed)
                    if self.RequesterChecker(response) == False:
                        return response
                    soup = BeautifulSoup(response.content, 'html.parser')
                    elements = soup.select('#container > div > section:nth-of-type(2) > div:nth-of-type(1) > div:nth-of-type(2) > ul > li > a')
                    pre_urlList = [element['href'] for element in elements]
                    self.IntegratedDB['UrlCnt'] += len(pre_urlList)
                    for url in pre_urlList:
                        urlList.append(url)
                    
                    for url in pre_urlList:
                        if url in previous_urls:
                            self.lastpage = True
                            break
            
            returnData = {
                'urlList': urlList,
                'urlCnt': len(urlList)
            }
            # return part
            return returnData
                
        except Exception:
            error_msg  = self.error_detector(self.error_detector_option)

    def parse_date(self, date_str):
        current_year = datetime.now().year  # 현재 연도 가져오기

        # 날짜와 시간을 분리
        date_part = date_str.split()[0]

        # 날짜가 'MM.DD' 형식인지 'YYYY.MM.DD' 형식인지 확인
        if len(date_part.split('.')) == 2:
            # 연도가 없는 경우
            date_part = f"{current_year}.{date_part}"
        
        # 날짜를 'YYYY-MM-DD' 형식으로 변환
        parsed_date = datetime.strptime(date_part, "%Y.%m.%d").strftime("%Y-%m-%d")

        return parsed_date
    
    def clean_html_with_regex(self, html_text):
        # <a> 태그 내부의 텍스트만 추출하고, 나머지 태그는 제거
        cleaned_text = re.sub(r'<a\s+[^>]*>(.*?)<\/a>', r'\1', html_text)
        return cleaned_text
    
    # Sync Part

    # 파라미터로 (url) 전달
    def articleCollector(self, artURL, speed):
        if isinstance(artURL, str) == False:
            return self.error_dump(2004, "Check artURL", artURL)
        
        try:
            #printStatus
            
            res = self.Requester_get(artURL)
            time.sleep(speed)
            if self.RequesterChecker(res) == False:
                return res
            bs            = BeautifulSoup(res.text, 'html.parser')
            art          = ''.join((i.text.replace("\n", "").replace("\u200b", "") for i in bs.select("#container > section > article:nth-child(3) > div.view_content_wrap > div > div.inner.clear > div.writing_view_box > div")))
            try:
                article_title = bs.select("#container > section > article:nth-child(3) > div.view_content_wrap > header > div > h3 > span.title_subject")[0].text.replace("\n", " ") # article_title
                date_obj  = bs.find("span", {"class": "gall_date"}).text.replace("\n", " ")
                article_date = date_obj[:11].replace('.','-')
                article_time = date_obj[-8:]
                article_esno = bs.select("#e_s_n_o")[0]["value"]

                articleData = [artURL, article_title, art, article_date, article_time, article_esno]
            except:
                articleData = []

            returnData = {
                'articleData': articleData
            }
            self.IntegratedDB['TotalArticleCnt'] += 1
            if self.print_status_option == True:
                "printStatus"
                #self.printStatus('NaverNews', 3, self.PrintData)

            return returnData
               
        except Exception as e:
            error_msg  = self.error_detector(self.error_detector_option)
            return self.error_dump(2005, error_msg, artURL)
    
    # 파라미터로 (url, 통계데이터 반환 옵션, 댓글 코드 반환 옵션) 전달
    def replyCollector(self, artURL, speed, article_esno):
        if isinstance(artURL, str) == False:
            return self.error_dump(2006, "Check artURL", artURL)
        
        try:
            pattern = r'[?&]([^=&]+)=([^&]+)'

            # 파라미터 추출
            matches = re.findall(pattern, artURL)
            
            #갤러리 종류 추출
            mgallery_pattern = re.compile(r'/mgallery')
            mini_pattern = re.compile(r'/mini')
            mgallery_match = mgallery_pattern.search(artURL)
            mini_match = mini_pattern.search(artURL)
            
            if mgallery_match:
                GALLTYPE = "M"
            elif mini_match:
                GALLTYPE = "MI"
            else:
                GALLTYPE = "G"
            # 결과 출력
            parameters = {match[0]: match[1] for match in matches}

            api_url = "https://gall.dcinside.com/board/comment/"
            page = 1
            headers = {
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Accept-Language": "ko-KR,ko;q=0.9",
                "Connection": "keep-alive",
                "Host": "gall.dcinside.com",
                "Origin": "https://gall.dcinside.com",
                "Referer": artURL,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
                "X-Requested-With": "XMLHttpRequest"
            }  
            # 요청 데이터
            

            no_list = []
            user_id_list = []
            name_list = []
            ip_list = []
            c_no_list = []
            depth_list = []
            reg_date_list = []
            reg_time_list = []
            is_delete_list = []
            memo_list = []
            replyList = []
            
            returnData = {
                'replyList': replyList,
                'replyCnt' : len(replyList)
            }
            self.replylastpage = False
            try:
                while not self.replylastpage:
                    try:
                        data = {
                            "id": parameters["id"],
                            "no": parameters["no"],
                            "cmt_id": parameters["id"],
                            "cmt_no": parameters["no"],
                            "focus_cno": "",
                            "focus_pno": "",
                            "e_s_n_o": article_esno,
                            "comment_page": str(page),
                            "sort": "",
                            "prevCnt": "",
                            "board_type": "",
                            "_GALLTYPE_": GALLTYPE
                        }
                        response = self.Requester_post(api_url, headers=headers, data=data)
                        time.sleep(speed)
                        temp = response.text
                        if not temp:
                            time.sleep(speed)
                            response = self.Requester_post(api_url, headers=headers, data=data)
                            temp = response.text
                            
                        temp = json.loads(temp)

                        # 댓글 목록에서 특정 name을 제거하는 로직
                        if temp['comments'] == None:
                            break
                        name_to_remove = "댓글돌이"
                        filtered_comments = [comment for comment in temp['comments'] if comment['name'] != name_to_remove]
                        temp['comments'] = filtered_comments

                        # 데이터를 저장하거나 처리하는 로직 추가 가능
                        

                        no = []
                        user_id = []
                        name = []
                        ip = []
                        c_no = []
                        depth = []
                        reg_date = []
                        reg_time = []
                        is_delete = []
                        memo = []
                        
                        df = pd.DataFrame(temp['comments'])

                        try:
                            no = list(df['no'])
                            user_id = list(df['user_id'])
                            name = list(df['name'])
                            ip = list(df['ip'])
                            c_no = list(df["c_no"])
                            depth = list(df['depth'])
                            reg_date = list(df['reg_date'])
                            reg_time = [time[-8:] for time in reg_date]
                            reg_date = [self.parse_date(str(i)) for i in reg_date]
                            is_delete = list(df['is_delete'])
                            memo = list(df['memo'])
                        except Exception as E:
                            if self.print_status_option:
                                "printStatus"
                                #self.printStatus('NaverNews', 4, self.PrintData)
                            return returnData

                        no_list.extend(no)
                        user_id_list.extend(user_id)
                        name_list.extend(name)
                        ip_list.extend(ip)
                        c_no_list.extend(c_no)
                        depth_list.extend(depth)
                        reg_date_list.extend(reg_date)
                        reg_time_list.extend(reg_time)
                        is_delete_list.extend(is_delete)
                        memo_list.extend(memo)

                        self.IntegratedDB['TotalReplyCnt'] += len(no)
                        
                        if self.print_status_option:
                            "printStatus"
                            #self.printStatus('NaverNews', 4, self.PrintData)
                            
                        if temp['total_cnt'] == len(no_list):
                            self.replylastpage = True
                
                        page += 1
                    except Exception as e:
                        return self.error_dump(1003, self.error_detector(), artURL)

                for i in range(temp['total_cnt']):
                    if memo_list[i][:10] == '<img class':
                        memo_list[i] = '<img>'
                    elif memo_list[i][:12] == '<video class':
                        memo_list[i] = '<vid>'
                    elif memo_list[i][-9:] == ' - dc App':
                        memo_list[i] = memo_list[i][:-9]
                    replyList.append(
                        [
                            str(i+1),
                            str(no_list[i]),
                            str(user_id_list[i]),
                            str(name_list[i]),
                            str(ip_list[i]),
                            str(c_no_list[i]),
                            str(depth_list[i]),
                            str(reg_date_list[i]),
                            str(reg_time_list[i]),
                            str(is_delete_list[i]),
                            str(self.clean_html_with_regex(html.unescape(memo_list[i]))),
                            str(artURL)
                        ]
                    )
                
                if self.print_status_option:
                    "printStatus"
                    #self.printStatus('NaverNews', 4, self.PrintData)

                returnData['replyList']           = replyList
                returnData['replyCnt']            = len(replyList)

                return returnData

            except Exception as e:
                error_msg  = self.error_detector(self.error_detector_option)
                return self.error_dump(2007, error_msg, artURL)
            
        except Exception as e:
            error_msg  = self.error_detector(self.error_detector_option)
            return self.error_dump(2007, error_msg, artURL)


if __name__ == "__main__":
    Crawler_obj = DCinsideCrawler()
    Crawler_obj.articleCollector("https://m.dcinside.com/board/hanmath/7268299", 3)
