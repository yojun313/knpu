import os
import sys

CRAWLER_PATH        = os.path.dirname(os.path.abspath(__file__))
COLLECTION_PATH     = os.path.join(CRAWLER_PATH, 'Collection')

from Package.NaverCrawlerPackage.NaverCafeCrawlerModule import NaverCafeCrawler
from Package.CrawlerModule import CrawlerModule
from Package.GoogleModule import GoogleModule

import warnings
import urllib3
import time
from datetime import datetime
import copy
import asyncio
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

class RealTimeCRAWLER(CrawlerModule):
    def __init__(self, keyword, checkPage):
        super().__init__(proxy_option=True)

        self.speed = 10
        self.checkPage              = checkPage
        self.checkwordList          = self.read_txt(COLLECTION_PATH + '/RealTime_wordList.txt')
        self.RealTimeCrawler_DBpath = self.pathFinder()['RealTimeCrawler_DBPath']
        self.crawlcom               = self.pathFinder()['computer_name']
        self.keyword                = keyword

        self.startTime = time.time()
        self.now = datetime.now()

    def InfoRecorder(self, msg):
        log = open(os.path.join(self.DBpath, self.DBname + '_INFO.txt'), 'w')
        log_msg = self.info_msg + msg
        log.write(log_msg)
        log.close()
    def DBMaker(self, DBtype):
        self.DBname = f'RealTimeCrawler_{DBtype}_{self.keyword}_{self.now.strftime('%m%d_%H%M')}'
        self.DBpath = os.path.join(self.RealTimeCrawler_DBpath, self.DBname)

        try:
            os.mkdir(self.DBpath)
            self.info_msg = (
                f"====================================================================================================================\n"
                "[Real Time CRAWLER]\n"
                f"{'Keyword:':<15} {self.keyword}\n"
                f"{'Computer:':<15} {self.crawlcom}\n"
                f"{'DB path:':<15} {self.DBpath}\n"
                f"{'Check Page:':<15} {self.checkPage}\n"
                f"{'Crawler Speed:':<15} {self.speed}\n"
                f"====================================================================================================================\n\n"
            )
            self.InfoRecorder('')

            log = open(os.path.join(self.DBpath, self.DBname + '_log.txt'), 'w+')
            log.write(self.info_msg + '\n\n')
            log.close()
        except:
            print("ERROR: DB 폴더 생성 실패 --> 잠시 후 다시 시도하세요")
            sys.exit()

    def ReturnChecker(self, value):
        if isinstance(value, dict) == True:
            first_key = list(value.keys())[0]
            if first_key == 'Error Code':
                err_msg_title = self.error_extractor(value['Error Code'])
                err_msg_content = value['Error Msg']
                err_target = value['Error Target']

                log = open(os.path.join(self.DBpath, self.DBname + '_log.txt'), 'a')
                msg = (
                    f"\n\nError Time: {self.now}\n"
                    f"Error Type: {err_msg_title}\n"
                    f"Error Detail: {err_msg_content}\n"
                    f"Error Target: {err_target}\n\n\n"
                )
                log.write(msg)
                log.close()
                return False
            else:
                return True

    def print_status(self):
        out_str = (
            f"|| Time: {datetime.now().strftime("%H:%M:%S")} "
            f"| Safe Article: {len(self.safe_article_list)-1} "
            f"| Safe Reply: {len(self.safe_reply_list)-1} "
            f"| Danger Article: {len(self.danger_article_list)-1} "
            f"| Danger Reply: {len(self.danger_reply_list)-1} ||"
        )
        self.InfoRecorder(out_str)
        print('\r'+out_str, end = '')

    def DangerChecker(self, text, title = ''):
        is_dangerous = False
        for word in self.checkwordList:
            if word in text:
                text = text.replace(word, f"{word}(DANGER)")
                is_dangerous = True
            if title != '' and word in title:
                title = title.replace(word, f"{word}(DANGER)")
                is_dangerous = True

        if is_dangerous == True:
            pass # 여기에 나중에 메일 알림 기능 넣기

        CheckResult = {
            'is_dangerous': is_dangerous,
            'text': text,
            'title': title
        }
        return CheckResult

    def RealTimeNaverCafeCrawler(self):

        NaverCafeCrawler_obj = NaverCafeCrawler(proxy_option=True, print_status_option=False)
        NaverCafeCrawler_obj.setCrawlSpeed(self.speed)

        self.DBtype = 'NaverCafe'
        self.DBMaker(self.DBtype)

        self.urlList   = []
        self.safe_article_list   = [["NaverCafe Name", "NaverCafe MemberCount", "Article Writer", "Article Title", "Article Text", "Article Date", "Article ReadCount", "Article ReplyCount", "Article URL"]]
        self.safe_reply_list     = [["Reply Num", "Reply Writer", "Reply Date", 'Reply Text', 'Article URL']]
        self.danger_article_list = copy.deepcopy(self.safe_article_list)
        self.danger_reply_list   = copy.deepcopy(self.safe_reply_list)
        self.checkedIDList       = []

        print(self.info_msg)

        while True:

            self.ListToCSV(object_list=self.safe_article_list, csv_path=self.DBpath, csv_name=self.DBname + '_SafeArticle.csv')
            self.ListToCSV(object_list=self.safe_reply_list, csv_path=self.DBpath, csv_name=self.DBname + '_SafeReply.csv')
            self.ListToCSV(object_list=self.danger_article_list, csv_path=self.DBpath, csv_name=self.DBname + '_DangerArticle.csv')
            self.ListToCSV(object_list=self.danger_reply_list, csv_path=self.DBpath, csv_name=self.DBname + '_DangerReply.csv')

            #print('\rCollecting Article...', end = '')
            urlList_returnData = NaverCafeCrawler_obj.RealTimeurlCollector(self.keyword, self.checkPage, self.checkedIDList)
            if self.ReturnChecker(urlList_returnData) == False:
                continue
            self.urlList = urlList_returnData['urlList']


            if len(self.urlList) == 0:
                self.print_status()
                time.sleep(1)
                continue

            for url in self.urlList:
                self.checkedIDList.append(NaverCafeCrawler_obj.articleIDExtractor(url))

            FullreturnData = asyncio.run(NaverCafeCrawler_obj.asyncMultiCollector(self.urlList, 2))

            for returnData in FullreturnData:

                article_returnData = returnData['articleData']
                if self.ReturnChecker(article_returnData) == True and article_returnData['articleData'] != []:
                    CheckResult = self.DangerChecker(article_returnData['articleData'][4], article_returnData['articleData'][3])

                    if CheckResult['is_dangerous'] == True:
                        article_returnData['articleData'][4] = CheckResult['text']
                        article_returnData['articleData'][3] = CheckResult['title']
                        self.danger_article_list.append(article_returnData['articleData'])
                    else:
                        self.safe_article_list.append(article_returnData['articleData'])

                    self.print_status()

                replyList_returnData = returnData['replyData']
                if self.ReturnChecker(replyList_returnData) == True:
                    for replyCnt in range(replyList_returnData['replyCnt']):
                        replyData = replyList_returnData['replyList'][replyCnt]
                        checkResult = self.DangerChecker(replyData[3]) # text 부분

                        if checkResult['is_dangerous'] == True:
                            replyData[3] = checkResult['text']
                            replyList_returnData['replyList'][replyCnt] = replyData
                            self.danger_reply_list.append(replyData)
                        else:
                            self.safe_reply_list.append(replyData)
                    self.print_status()

def controller():
    """
    print("================ Crawler Controller ================")
    print("\n[ 실시간 크롤링 대상 ]\n")
    print("1. Naver Cafe")

    while True:
        control_ask = int(input("\n입력: "))
        if control_ask in [1,2]:
            break
        else:
            print("다시 입력하세요")

    keyword   = input("\nKeyword: ")
    checkPage = int(input("\nPage: "))
    """

    control_ask = 1
    keyword = "대통령"
    checkPage = 2

    RealTimeCrawler_obj = RealTimeCRAWLER(keyword, checkPage)
    RealTimeCrawler_obj.clear_screen()

    if control_ask == 1:
        RealTimeCrawler_obj.RealTimeNaverCafeCrawler()

if __name__ == '__main__':
    controller()


#최우철 왓따 감
