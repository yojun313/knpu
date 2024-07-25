# -*- coding: utf-8 -*-
import os
import sys

NAVERCRAWLERPACKAGE_PATH = os.path.dirname(os.path.abspath(__file__))
PACKAGE_PATH = os.path.dirname(NAVERCRAWLERPACKAGE_PATH)
sys.path.append(PACKAGE_PATH)

from CrawlerModule import CrawlerModule
from ToolModule import ToolModule
import json
from googleapiclient.discovery import build
from bs4 import BeautifulSoup
from datetime import datetime
import sys
import re


class YouTubeCrawler(CrawlerModule):

    def __init__(self, proxy_option=False, print_status_option=False):
        super().__init__(proxy_option)
        self.print_status_option = print_status_option


        self.api_dic = {}
        self.api_list = self.read_txt(os.path.join(self.collection_path, 'YouTube_apiList.txt'))
        self.api_num = 1
        self.api_obj = build('youtube', 'v3', developerKey=self.api_list[self.api_num - 1])

        for num in range(1, len(self.api_list)):
            self.api_dic[num] = self.api_list[num - 1]

    def urlCollector(self, keyword, startDate, endDate):
        urlLimiter = ['playlist', 'shorts', 'channel', 'user', 'm.']
        site = 'youtube.com'
        startDate = datetime.strptime(str(startDate), "%Y%m%d").strftime("%-m/%-d/%Y")
        endDate = datetime.strptime(str(endDate), "%Y%m%d").strftime("%-m/%-d/%Y")
        currentPage = 0

        urlList = []

        try:
            if self.print_status_option == True:
                self.IntegratedDB['UrlCnt'] = 0
                self.printStatus('YouTube', 1, self.PrintData)

            while True:
                search_page_url = 'https://www.google.co.kr/search?q={}+site:{}&hl=ko&source=lnt&tbs=cdr%3A1%2Ccd_min%3A{}%2Ccd_max%3A{}&tbm=vid&start={}'.format(
                    keyword, site, startDate, endDate, currentPage)
                header = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                cookie = {'CONSENT': 'YES'}

                main_page = self.Requester(search_page_url, headers=header, cookies=cookie)
                main_page = BeautifulSoup(main_page.text, "lxml")
                site_result = main_page.select("a[jsname = 'UWckNb']")

                if site_result == []:
                    break

                for a in site_result:
                    add_link = a['href']

                    if add_link not in urlList and 'https://www.youtube.com/' in add_link and '@' not in add_link:
                        # Check if the URL contains any characters from urlLimiter
                        contains_limiter = False
                        for char in urlLimiter:
                            if char in add_link:
                                contains_limiter = True
                                break

                        if contains_limiter == False:
                            urlList.append(add_link)
                            self.IntegratedDB['UrlCnt'] += 1

                if self.print_status_option == True:
                    self.printStatus('YouTube', option=2, printData=self.PrintData)
                currentPage += 10

            urlList = list(set(urlList))
            returnData = {
                'urlList': urlList,
                'urlCnt': len(urlList)
            }

            return returnData

        except Exception as e:
            self.error_detector()

    def articleCollector(self, url):

        if 'https://www.youtube.com/watch?v=' not in url:
            self.error_dump(2025, "Check YouTubeURL", url)
            return self.error_data

        try:
            returnData = {
                'articleData': []
            }
            youtube_info = url[32:]
            info_api_url = "https://hadzy.com/api/videos/{}".format(youtube_info)

            main_page = self.Requester(info_api_url)

            try:
                temp = json.loads(main_page.text)
                channel = temp['items'][0]['snippet']['channelTitle']  # 채널 이름
                video_url = url  # url
                video_title = temp['items'][0]['snippet']['title'].replace("\n", " ").replace("\r", "").replace("\t",
                                                                                                                "").replace(
                    "<br>", " ")  # 영상 제목
                video_description = temp['items'][0]['snippet']['description'].replace("\n", "").replace("\t",
                                                                                                         "").replace(
                    "\r", "").replace("<br>", " ")  # 영상 설명
                video_date = temp['items'][0]['snippet']['publishedAt']  # 영상 날짜
                video_date = datetime.strptime(video_date, "%Y-%m-%dT%H:%M:%S%z").strftime("%Y-%m-%d")
                view_count = temp['items'][0]['statistics']['viewCount']  # 조회수
                like_count = temp['items'][0]['statistics']['likeCount']  # 좋아요
                comment_count = temp['items'][0]['statistics']['commentCount']  # 댓글 수
            except:
                return returnData

            self.IntegratedDB['TotalArticleCnt'] += 1
            if self.print_status_option == True:
                self.printStatus('YouTube', 3, self.PrintData)

            articleData = [channel, video_url, video_title, video_description, video_date, view_count, like_count,
                           comment_count]
            returnData['articleData'] = articleData
            return returnData

        except Exception:
            error_msg = self.error_detector(self.error_detector_option)
            self.error_dump(2026, error_msg, url)
            return self.error_data

    # noinspection RegExpRedundantEscape
    def replyCollector(self, url, option):
        if 'https://www.youtube.com/watch?v=' not in url:
            self.error_dump(2027, "Check YouTubeURL", url)
            return self.error_data

        try:
            youtube_info = url[32:]
            replyList = []
            rereplyList = []
            reply_idx = 1
            rereply_idx = 1

            while True:
                try:
                    request = self.api_obj.commentThreads().list(part='snippet,replies', videoId=youtube_info,
                                                                 maxResults=100, order='relevance')
                    response = request.execute()
                    break
                except Exception as e:
                    if any(error in str(e) for error in
                           ["operationNotSupported", "commentsDisabled", "forbidden", "channelNotFound",
                            "commentThreadNotFound", "videoNotFound", "processingFailure"]):
                        return {'replyList': [], 'rereplyList': [], 'replyCnt': 0, 'rereplyCnt': 0,
                                'api_num': self.api_num}
                    elif "quotaExceeded" in str(e):
                        if self.api_num == len(self.api_list):
                            print("\rAPI 할당량 초과 --> 1일 후 유튜브 크롤링을 시도해주십시오")
                            sys.exit()
                        self.api_num += 1
                        self.PrintData['api_num'] = self.api_num
                        self.api_obj = build('youtube', 'v3', developerKey=self.api_list[self.api_num - 1])

            while request:
                for item in response['items']:
                    try:
                        comment = item['snippet']['topLevelComment']['snippet']
                        textdisplay = comment['textDisplay'].replace('<br>', ' ')
                        if '</a>' in textdisplay:
                            textdisplay = re.sub(r'<a[^>]*>(.*?)<\/a>', '', textdisplay)
                            textdisplay = textdisplay[1:]
                        replyData = [reply_idx, comment['authorDisplayName'], datetime.strptime(comment['publishedAt'], "%Y-%m-%dT%H:%M:%S%z").strftime("%Y-%m-%d"), textdisplay,
                                     comment['likeCount'], url]
                        replyList.append(replyData)

                        reply_idx += 1
                        self.IntegratedDB['TotalReplyCnt'] += 1

                        try:
                            if item['snippet']['totalReplyCount'] > 0:
                                for reply_item in item['replies']['comments']:
                                    reply = reply_item['snippet']
                                    rereplyList.append([rereply_idx, reply['authorDisplayName'], datetime.strptime(comment['publishedAt'], "%Y-%m-%dT%H:%M:%S%z").strftime("%Y-%m-%d"),
                                                        reply['textDisplay'], reply['likeCount'], url])
                                    rereply_idx += 1
                                    self.IntegratedDB['TotalRereplyCnt'] += 1
                        except Exception as e:
                            pass
                    except Exception as e:
                        pass

                if self.print_status_option == True:
                    self.printStatus('YouTube', 6, self.PrintData)

                if option == 2:
                    if 'nextPageToken' in response:
                        while True:
                            try:
                                request = self.api_obj.commentThreads().list(part='snippet,replies',
                                                                             videoId=youtube_info,
                                                                             pageToken=response['nextPageToken'],
                                                                             maxResults=100, order='relevance')
                                response = request.execute()
                                break
                            except Exception as e:
                                if any(error in str(e) for error in
                                       ["operationNotSupported", "commentsDisabled", "forbidden", "channelNotFound",
                                        "commentThreadNotFound", "videoNotFound", "processingFailure"]):
                                    return {'replyList': replyList, 'rereplyList': rereplyList,
                                            'replyCnt': len(replyList), 'rereplyCnt': len(rereplyList),
                                            'api_num': self.api_num}
                                elif "quotaExceeded" in str(e):
                                    if self.api_num == len(self.api_list):
                                        print("\rAPI 할당량 초과 --> 1일 후 유튜브 크롤링을 시도해주십시오")
                                        sys.exit()
                                    self.api_num += 1
                                    self.PrintData['api_num'] = self.api_num
                                    self.api_obj = build('youtube', 'v3', developerKey=self.api_list[self.api_num - 1])
                    else:
                        return {'replyList': replyList, 'rereplyList': rereplyList, 'replyCnt': len(replyList),
                                'rereplyCnt': len(rereplyList), 'api_num': self.api_num}
                else:
                    return {'replyList': replyList, 'rereplyList': rereplyList, 'replyCnt': len(replyList),
                            'rereplyCnt': len(rereplyList), 'api_num': self.api_num}

        except Exception:
            error_msg = self.error_detector(self.error_detector_option)
            self.error_dump(2028, error_msg, url)
            return self.error_data

    def syncSingleCollector(self, url, option):
        articleData = self.articleCollector(url)
        replyData = self.replyCollector(url, option)
        return {'articleData': articleData, 'replyData': replyData}

    def syncMultiCollector(self, urlList, option):
        results = []
        for url in urlList:
            results.append(self.syncSingleCollector(url, option))
        return results

def syncTester():
    print("============ Crawler Packeage Tester ============")
    print("I. Choose Option\n")
    print("1. ALL  (Full Automatic: UrlCollector -> articleCollector & replyCollector)")
    print("2. Part (YouTubeURL Required -> articleCollector & replyCollector)\n")

    number       = int(input("Number: "))
    proxy_option = int(input("\nUse Proxy? (1/0): "))
    option       = int(input("\nOption: "))
    print("==================================================")

    CrawlerPackage_obj = YouTubeCrawler(proxy_option=proxy_option, print_status_option=True)
    CrawlerPackage_obj.error_detector_option_on()

    if number == 1:
        print("\nNaverNewsCrawler_urlCollector: ", end='')
        urlList_returnData = CrawlerPackage_obj.urlCollector("대통령", 20240601, 20240601)
        urlList = urlList_returnData['urlList']

        results = CrawlerPackage_obj.syncMultiCollector(urlList, option)
        print('\n')
        for i in results:
            print(i)

    elif number == 2:
        url = input("\nTarget NaverNews URL: ")
        result = CrawlerPackage_obj.sycSingleCollector(url, option)
        print(result)



if __name__ == "__main__":
    syncTester()
