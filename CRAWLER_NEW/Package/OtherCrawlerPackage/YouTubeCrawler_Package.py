# -*- coding: utf-8 -*-
import sys
import os

NAVERCRAWLERPACKAGE_PATH = os.path.dirname(os.path.abspath(__file__))
PACKAGE_PATH      = os.path.dirname(NAVERCRAWLERPACKAGE_PATH)
sys.path.append(PACKAGE_PATH)

from CrawlerPackage import CrawlerPackage
from ToolPackage import ToolPackage
import json
from googleapiclient.discovery import build
import sys
import re

class YouTubeCrawler(CrawlerPackage):
    
    def __init__(self, proxy_option = False):
        super().__init__(proxy_option)
        self.error_data = {
            'Error Code' : 1,
            'Error Msg' : "",
            'Error Target' : ""
        }
        
        self.api_dic        = {}
        self.api_list       = self.read_txt(os.path.join(self.collection_path, 'YouTube_apiList.txt'))
        self.api_num        = 1
        self.api_obj        = build('youtube', 'v3', developerKey=self.api_list[self.api_num - 1])
        
        for num in range(1, len(self.api_list)):
            self.api_dic[num] = self.api_list[num-1]

    def urlCollector(self, keyword, startDate, endDate):
        return super().urlCollector(keyword, startDate, endDate, site='youtube.com', urlLimiter=['playlist', 'shorts', 'channel', 'user', 'm.'])
    
    def articleCollector(self, url, error_detector_option = False):
        
        if 'https://www.youtube.com/watch?v=' not in url:
            self.error_dump(2025, "Check YouTubeURL", url)
            return self.error_data
        
        try:
            youtube_info = url[32:]
            info_api_url = "https://hadzy.com/api/videos/{}".format(youtube_info)
            
            main_page = self.Requester(info_api_url)
            
            try:
                temp = json.loads(main_page.text)
                channel = temp['items'][0]['snippet']['channelTitle'] # 채널 이름
                video_url = url # url
                video_title = temp['items'][0]['snippet']['title'].replace("\n", " ").replace("\r", "").replace("\t", "").replace("<br>"," ") # 영상 제목
                video_description = temp['items'][0]['snippet']['description'].replace("\n","").replace("\t","").replace("\r", "").replace("<br>"," ") # 영상 설명
                video_date = temp['items'][0]['snippet']['publishedAt']  # 영상 날짜
                view_count = temp['items'][0]['statistics']['viewCount']  # 조회수
                like_count = temp['items'][0]['statistics']['likeCount']  # 좋아요
                comment_count = temp['items'][0]['statistics']['commentCount']  # 댓글 수
            except:
                return []
            
            articleData = [channel, video_url, video_title, video_description, video_date, view_count, like_count, comment_count]
            returnData = {
                'articleData' : articleData
            }
            return returnData

        except Exception:
            error_msg  = self.error_detector(error_detector_option)
            self.error_dump(2026, error_msg, url)
            return self.error_data
            
    def replyCollector(self, url, limiter = True, error_detector_option = False):
        if 'https://www.youtube.com/watch?v=' not in url:
            self.error_dump(2027, "Check YouTubeURL", url)
            return self.error_data
        
        try:
            youtube_info = url[32:]
            replyList = []
            
            while True:
                try:
                    request = self.api_obj.commentThreads().list(part='snippet,replies', videoId = youtube_info, maxResults=100, order = 'relevance')
                    response = request.execute()
                    break
                except Exception as e:
                    if any(error in str(e) for error in ["operationNotSupported", "commentsDisabled", "forbidden", "channelNotFound", "commentThreadNotFound", "videoNotFound", "processingFailure"]):
                        return {'replyList': [], 'replyCnt': 0, 'api_num' : self.api_num}
                    elif "quotaExceeded" in str(e):
                        if self.api_num == len(self.api_list):
                            print("\rAPI 할당량 초과 --> 1일 후 유튜브 크롤링을 시도해주십시오")
                            sys.exit()
                        self.api_num += 1
                        self.api_obj = build('youtube', 'v3', developerKey=self.api_list(self.api_num - 1))
            
            while request:
                for item in response['items']:
                    try:
                        comment = item['snippet']['topLevelComment']['snippet']
                        textdisplay = comment['textDisplay'].replace('<br>', ' ')
                        if '</a>' in textdisplay:
                            textdisplay = re.sub(r'<a[^>]*>(.*?)<\/a>', '', textdisplay)
                            textdisplay = textdisplay[1:]
                        replyList.append([comment['authorDisplayName'], comment['publishedAt'], textdisplay, comment['likeCount'], url])
                        """
                        if self.option == 2:
                            try:
                                if item['snippet']['totalReplyCount'] > 0:
                                    for reply_item in item['replies']['comments']:
                                        reply = reply_item['snippet']
                                        replyList.append([reply['textDisplay'], reply['authorDisplayName'], reply['publishedAt'], reply['likeCount']])
                            except:
                                pass
                        """
                    except:
                        pass 
                
                if limiter == False:
                    if 'nextPageToken' in response:
                        while True:
                            try:
                                request = self.api_obj.commentThreads().list_next(request, response)
                                response = request.execute()
                                break
                            except Exception as e:
                                if any(error in str(e) for error in ["operationNotSupported", "commentsDisabled", "forbidden", "channelNotFound", "commentThreadNotFound", "videoNotFound", "processingFailure"]):
                                    return []
                                elif "quotaExceeded" in str(e):
                                    if self.api_num == len(self.api_list):
                                        print("\rAPI 할당량 초과 --> 1일 후 유튜브 크롤링을 시도해주십시오")
                                        sys.exit()
                                    self.api_num += 1
                                    self.api_obj = build('youtube', 'v3', developerKey=self.api_list(self.api_num - 1))
                    else:
                        return {'replyList': replyList, 'replyCnt': 0, 'api_num' : self.api_num}
                else:
                    return {'replyList': replyList, 'replyCnt': 0, 'api_num' : self.api_num}
        
        except Exception:
            error_msg  = self.error_detector(error_detector_option)
            self.error_dump(2028, error_msg, url)
            return self.error_data

def CrawlerTester(url):
    print("\nYouTubeCrawler_articleCollector: ", end = '')
    target = CrawlerPackage_obj.articleCollector(url=url, error_detector_option=True)
    ToolPackage_obj.CrawlerChecker(target, result_option=result_option)
    
    print("\nYouTubeCrawler_replyCollector: ", end = '')
    target = CrawlerPackage_obj.replyCollector(url=url, limiter=True, error_detector_option=True)
    ToolPackage_obj.CrawlerChecker(target, result_option=result_option)
    
            
if __name__ == "__main__":
    ToolPackage_obj = ToolPackage()
    
    print("============ Crawler Packeage Tester ============")
    print("I. Choose Option\n")
    print("1. ALL  (Full Automatic: UrlCollector -> articleCollector & replyCollector)")
    print("2. Part (YouTubeURL Required -> articleCollector & replyCollector)\n")
    
    option = int(input("Number: "))
    proxy_option = int(input("\nUse Proxy? (1/0): "))
    result_option = int(input("\nPrint Result (1/0): "))
    print("==================================================")
    
    CrawlerPackage_obj = YouTubeCrawler(proxy_option=proxy_option)
    
    if option == 1:
        print("\nYouTubeCrawler_urlCollector: ", end = '')
        returnData = CrawlerPackage_obj.urlCollector("급발진", 20240601, 20240601)
        ToolPackage_obj.CrawlerChecker(returnData, result_option=result_option)
        
        urlList = returnData['urlList']
        for url in urlList:
            CrawlerTester(url)
            
    elif option == 2:
        url = input("\nTarget YouTube URL: ")
        CrawlerTester(url)