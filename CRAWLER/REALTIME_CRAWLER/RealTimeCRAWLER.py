import os
import sys
import time
from datetime import datetime
from Package.NaverCrawlerPackage.NaverCafeCrawlerModule import NaverCafeCrawler
from Package.NaverCrawlerPackage.NaverBlogCrawlerModule import NaverBlogCrawler
from Package.NaverCrawlerPackage.NaverNewsCrawlerModule import NaverNewsCrawler
from Package.OtherCrawlerPackage.DcinsideCrawlerModule import DCinsideCrawler
from Package.CrawlerModule import CrawlerModule
import warnings
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=FutureWarning)


class RealTimeCRAWLER(CrawlerModule):
    def __init__(self, keyword, speed=5, checkPage=10, word_list_path=None):
        super().__init__()

        self.speed = speed  # 요청 간 대기 시간을 초 단위로 설정
        self.checkPage = checkPage  # 초기 수집값
        
        # 현재 EXE 실행 파일의 디렉토리 위치를 가져옴
        if getattr(sys, 'frozen', False):
            self.base_path = os.path.dirname(sys.executable)
        else:
            self.base_path = os.path.dirname(__file__)
        
        # 위험 단어 목록 파일 경로를 사용하여 로드
        if word_list_path:
            self.checkwordList = self.read_txt(word_list_path)
        else:
            self.checkwordList = self.read_txt(os.path.join(self.base_path, 'RealTime_wordList.txt'))
        
        self.RealTimeCrawler_DBpath = self.pathFinder()['RealTimeCrawler_DBPath']
        self.crawlcom = self.pathFinder()['computer_name']
        self.keyword = keyword
        self.RealTimeCrawler_DBpath = "C:/RealTimeCrawler_DB"
        print(f"저장 경로: {self.RealTimeCrawler_DBpath}")
        self.startTime = time.time()
        self.now = datetime.now()

        # 폴더가 없을 경우 자동으로 생성
        if not os.path.exists(self.RealTimeCrawler_DBpath):
            os.makedirs(self.RealTimeCrawler_DBpath)

        self.previous_urls = []  # 직전 수집한 10개의 URL을 저장

    def InfoRecorder(self, msg):
        log = open(os.path.join(self.DBpath, self.DBname + '_INFO.txt'), 'w')
        log_msg = self.info_msg + msg
        log.write(log_msg)
        log.close()

    def DBMaker(self, DBtype):
        self.DBname = f'RealTimeCrawler_{DBtype}_{self.keyword}_{self.now.strftime("%m%d_%H%M")}'
        self.DBpath = os.path.join(self.RealTimeCrawler_DBpath, self.DBname)

        try:
            os.makedirs(self.DBpath)
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
        except Exception as e:
            print("ERROR: DB 폴더 생성 실패 --> 잠시 후 다시 시도하세요")
            sys.exit()

    def ReturnChecker(self, value):
        if isinstance(value, dict):
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
            f"|| Time: {datetime.now().strftime('%H:%M:%S')} "
            f"| Safe Article: {len(self.safe_article_list) - 1} "
            f"| Safe Reply: {len(self.safe_reply_list) - 1} "
            f"| Danger Article: {len(self.danger_article_list) - 1} "
            f"| Danger Reply: {len(self.danger_reply_list) - 1} ||"
        )
        self.InfoRecorder(out_str)
        print('\r' + out_str, end='', flush=True)

    def DangerChecker(self, text, title=''):
        is_dangerous = False
        danger = ""
        for word in self.checkwordList:
            if word in text:
                text = text.replace(word, f"{word}(DANGER)")
                is_dangerous = True
                danger = word
            if title != '' and word in title:
                title = title.replace(word, f"{word}(DANGER)")
                is_dangerous = True

        CheckResult = {
            'is_dangerous': is_dangerous,
            'text': text,
            'title': title,
            'danger': danger
        }
        return CheckResult

    def check_for_duplicates(self, new_urls):
        # 새로운 URL 목록에서 중복된 URL이 나오면 그 이후 수집을 멈춤
        unique_urls = []
        for url in new_urls:
            if url in self.previous_urls:
                continue
            unique_urls.append(url)
        return unique_urls
    
    def RealTimeNaverCafeCrawler(self):
        NaverCafeCrawler_obj = NaverCafeCrawler(print_status_option=False)
        self.DBtype = 'NaverCafe'
        self.DBMaker(self.DBtype)

        self.urlList = []
        self.safe_article_list = [["NaverCafe Name", "NaverCafe MemberCount", "Article Writer", "Article Title", "Article Text", "Article Date", "Article Time", "Article ReadCount", "Article ReplyCount", "Article URL"]]
        self.safe_reply_list = [["Reply Num", "Reply Writer", "Reply Date", "Reply Time", 'Reply Text', 'Article URL']]
        self.danger_article_list = [["NaverCafe Name", "NaverCafe MemberCount", "Article Writer", "Article Title", "Article Text", "Article Date", "Article Time", "Article ReadCount", "Article ReplyCount", "Article URL", "Danger"]]
        self.danger_reply_list = [["Reply Num", "Reply Writer", "Reply Date", "Reply Time", 'Reply Text', 'Article URL', "Danger"]]
        self.previous_urls = []

        print(self.info_msg)

        while True:
            urlList_returnData = NaverCafeCrawler_obj.RealTimeurlCollector(self.keyword, self.checkPage, self.previous_urls, self.speed)
            self.checkPage = 0
            if not self.ReturnChecker(urlList_returnData):
                continue

            new_urls = urlList_returnData['urlList']
            unique_urls = self.check_for_duplicates(new_urls)

            if not unique_urls:
                self.print_status()
                time.sleep(10)  # 10초 대기
                continue

            self.urlList = unique_urls

            self.previous_urls = self.urlList + self.previous_urls
            self.previous_urls = self.previous_urls[:30]

            for url in self.urlList:
                articleData = NaverCafeCrawler_obj.articleCollector(url, self.speed)
                if articleData:
                    if articleData['articleData']:
                        try:
                            checkResult = self.DangerChecker(articleData['articleData'][4])
                            if checkResult['is_dangerous']:
                                articleData['articleData'].append(checkResult['danger'])
                                self.danger_article_list.append(articleData['articleData'])
                            else:
                                self.safe_article_list.append(articleData['articleData'])
                                
                        except Exception as e:
                            print(url)
                            print(e)

                try:
                    if not articleData['articleData'][8] == 0:
                        replyData = NaverCafeCrawler_obj.replyCollector(url, self.speed, articleData['cafeID'])
                        if replyData:
                            try:
                                if replyData['replyList']:
                                    for reply in replyData['replyList']:
                                        checkResult = self.DangerChecker(reply[3])
                                        if checkResult['is_dangerous']:
                                            reply.append(checkResult['danger'])
                                            self.danger_reply_list.append(reply)
                                        else:
                                            self.safe_reply_list.append(reply)
                                            
                            except Exception as e:
                                pass
                                        
                except Exception as e:
                    print(e)
                self.ListToCSV(object_list=self.safe_article_list, csv_path=self.DBpath, csv_name=self.DBname + '_SafeArticle.csv')
                self.ListToCSV(object_list=self.safe_reply_list, csv_path=self.DBpath, csv_name=self.DBname + '_SafeReply.csv')
                self.ListToCSV(object_list=self.danger_article_list, csv_path=self.DBpath, csv_name=self.DBname + '_DangerArticle.csv')
                self.ListToCSV(object_list=self.danger_reply_list, csv_path=self.DBpath, csv_name=self.DBname + '_DangerReply.csv')

            
                self.print_status()

    def RealTimeNaverBlogCrawler(self):
        NaverBlogCrawler_obj = NaverBlogCrawler(print_status_option=False)
        self.DBtype = 'NaverBlog'
        self.DBMaker(self.DBtype)

        self.urlList = []
        self.safe_article_list = [["BlogID", "URL", "Article Text", "Article Date", "Article Time"]]
        self.safe_reply_list = [["Reply Num", "Reply Writer", "Reply Date", "Reply Time", 'Reply Text', 'Article URL']]
        self.danger_article_list = [["BlogID", "URL", "Article Text", "Article Date", "Article Time", "Danger"]]
        self.danger_reply_list = [["Reply Num", "Reply Writer", "Reply Date", "Reply Time", 'Reply Text', 'Article URL', "Danger"]]
        self.previous_urls = []

        print(self.info_msg)

        while True:
            urlList_returnData = NaverBlogCrawler_obj.RealTimeurlCollector(self.keyword, self.checkPage, self.previous_urls, self.speed)
            self.checkPage = 0
            if not self.ReturnChecker(urlList_returnData):
                continue

            new_urls = urlList_returnData['urlList']
            unique_urls = self.check_for_duplicates(new_urls)

            if not unique_urls:
                self.print_status()
                time.sleep(10)  # 10초 대기
                continue

            self.urlList = unique_urls

            self.previous_urls = self.urlList + self.previous_urls
            self.previous_urls = self.previous_urls[:30]

            for url in self.urlList:
                articleData = NaverBlogCrawler_obj.articleCollector(url, self.speed)
                if articleData:
                    checkResult = self.DangerChecker(articleData['articleData'][2])
                    if checkResult['is_dangerous']:
                        articleData['articleData'].append(checkResult['danger'])
                        self.danger_article_list.append(articleData['articleData'])
                    else:
                        self.safe_article_list.append(articleData['articleData'])

                    replyData = NaverBlogCrawler_obj.replyCollector(url, self.speed)
                    if replyData:
                        try:
                            if replyData['replyList']:
                                for reply in replyData['replyList']:
                                    checkResult = self.DangerChecker(reply[4])
                                    if checkResult['is_dangerous']:
                                        reply.append(checkResult['danger'])
                                        self.danger_reply_list.append(reply)
                                    else:
                                        self.safe_reply_list.append(reply)
                                        
                        except Exception as e:
                            print(e)

                self.print_status()
                self.ListToCSV(object_list=self.safe_article_list, csv_path=self.DBpath, csv_name=self.DBname + '_SafeArticle.csv')
                self.ListToCSV(object_list=self.safe_reply_list, csv_path=self.DBpath, csv_name=self.DBname + '_SafeReply.csv')
                self.ListToCSV(object_list=self.danger_article_list, csv_path=self.DBpath, csv_name=self.DBname + '_DangerArticle.csv')
                self.ListToCSV(object_list=self.danger_reply_list, csv_path=self.DBpath, csv_name=self.DBname + '_DangerReply.csv')

    def RealTimeNaverNewsCrawler(self):
        NaverNewsCrawler_obj = NaverNewsCrawler(print_status_option=False)
        self.DBtype = 'NaverNews'
        self.DBMaker(self.DBtype)

        self.urlList = []
        self.safe_article_list = [["Article Press", "Article Type", "Article URL", "Article Title", "Article Text", "Article Date", "Article Time"]]
        self.safe_reply_list = [["Reply Num", "Reply Writer", "Reply Date", 'Reply Text', 'Article URL']]
        self.danger_article_list = [["Article Press", "Article Type", "Article URL", "Article Title", "Article Text", "Article Date", "Article Time", "Danger"]]
        self.danger_reply_list = self.safe_reply_list[:]
        self.previous_urls = []
        self.previous_urls = []

        print(self.info_msg)

        while True:
            urlList_returnData = NaverNewsCrawler_obj.RealTimeurlCollector(self.keyword, self.checkPage, self.previous_urls, self.speed)
            self.checkPage = 0
            if not self.ReturnChecker(urlList_returnData):
                continue

            new_urls = urlList_returnData['urlList']
            unique_urls = self.check_for_duplicates(new_urls)

            if not unique_urls:
                self.print_status()
                time.sleep(10)  # 10초 대기
                continue

            self.urlList = unique_urls

            self.previous_urls = self.urlList + self.previous_urls
            self.previous_urls = self.previous_urls[:30]

            for url in self.urlList:
                articleData = NaverNewsCrawler_obj.articleCollector(url, self.speed)
                if articleData:
                    checkResult = self.DangerChecker(articleData['articleData'][4])
                    if checkResult['is_dangerous']:
                        articleData['articleData'].append(checkResult['danger'])
                        self.danger_article_list.append(articleData['articleData'])
                    else:
                        self.safe_article_list.append(articleData['articleData'])
                    self.safe_article_list.append(articleData['articleData'])

                self.print_status()
                self.ListToCSV(object_list=self.safe_article_list, csv_path=self.DBpath, csv_name=self.DBname + '_SafeArticle.csv')
                self.ListToCSV(object_list=self.danger_article_list, csv_path=self.DBpath, csv_name=self.DBname + '_DangerArticle.csv')

    def RealTimeDCinsideCrawler(self):
        DCinsideCrawler_obj = DCinsideCrawler(print_status_option=False)
        self.DBtype = 'DCinside'
        self.DBMaker(self.DBtype)

        self.urlList = []
        self.safe_article_list = [["Article Url", "Article Title", "Article Text", "Article Date", "Article Time", "Article Esno"]]
        self.safe_reply_list = [["Reply Num", "Reply Writer", "Reply Date", "Reply Time", "Reply Text", "Article URL"]]
        self.danger_article_list = [["Article Url", "Article Title", "Article Text", "Article Date", "Article Time", "Article Esno", "Danger"]]
        self.danger_reply_list = [["Reply Num", "Reply Writer", "Reply Date", "Reply Time", "Reply Text", "Article URL", "Danger"]]
        self.previous_urls = []
        reply_indices_id = [1, 2, 7, 8, 10, 11]
        reply_indices_name = [1, 3, 7, 8, 10, 11]

        print(self.info_msg)

        while True:
            urlList_returnData = DCinsideCrawler_obj.RTurlCollector(self.keyword, self.checkPage, self.previous_urls, self.speed)
            self.checkPage = 0
            if not self.ReturnChecker(urlList_returnData):
                continue

            new_urls = urlList_returnData['urlList']
            unique_urls = self.check_for_duplicates(new_urls)

            if not unique_urls:
                self.print_status()
                time.sleep(10)  # 10초 대기
                continue

            self.urlList = unique_urls

            self.previous_urls = self.urlList + self.previous_urls
            self.previous_urls = self.previous_urls[:30]

            for url in self.urlList:
                articleData = DCinsideCrawler_obj.articleCollector(url, self.speed)
                if articleData:
                    if articleData["articleData"]:
                        checkResult = self.DangerChecker(articleData['articleData'][2])
                        if checkResult['is_dangerous']:
                            articleData['articleData'].append(checkResult['danger'])
                            self.danger_article_list.append(articleData['articleData'])
                        else:
                            self.safe_article_list.append(articleData['articleData'])

                        replyData = DCinsideCrawler_obj.replyCollector(url, self.speed, articleData['articleData'][-1])
                        if replyData:
                            try:
                                if replyData['replyList']:
                                    for reply in replyData['replyList']:
                                        if reply[2]:
                                            new_reply = [reply[i] for i in reply_indices_id]
                                        else:
                                            new_reply = [reply[i] for i in reply_indices_name]
                                        checkResult = self.DangerChecker(reply[10])
                                        if checkResult['is_dangerous']:
                                            new_reply.append(checkResult['danger'])
                                            self.danger_reply_list.append(new_reply)
                                        else:
                                            self.safe_reply_list.append(new_reply)
                                    
                            except Exception as e:
                                print(e)

                self.print_status()
                self.ListToCSV(object_list=self.safe_article_list, csv_path=self.DBpath, csv_name=self.DBname + '_SafeArticle.csv')
                self.ListToCSV(object_list=self.safe_reply_list, csv_path=self.DBpath, csv_name=self.DBname + '_SafeReply.csv')
                self.ListToCSV(object_list=self.danger_article_list, csv_path=self.DBpath, csv_name=self.DBname + '_DangerArticle.csv')
                self.ListToCSV(object_list=self.danger_reply_list, csv_path=self.DBpath, csv_name=self.DBname + '_DangerReply.csv')

                


def controller():
    print("================ Crawler Controller ================")
    print("\n[ 실시간 크롤링 대상 ]\n")
    print("1. Naver Cafe")
    print("2. Naver Blog")
    print("3. Naver News")
    print("4. DCinside")

    control_ask = int(input("\n입력: "))
    keyword = input("\nKeyword: ")
    speed = int(input("\nSpeed: "))
    checkPage = int(input("\nPage(1 이상): "))

    RealTimeCrawler_obj = RealTimeCRAWLER(keyword, speed, checkPage)
    RealTimeCrawler_obj.clear_screen()

    if control_ask == 1:
        RealTimeCrawler_obj.RealTimeNaverCafeCrawler()
    elif control_ask == 2:
        RealTimeCrawler_obj.RealTimeNaverBlogCrawler()
    elif control_ask == 3:
        RealTimeCrawler_obj.RealTimeNaverNewsCrawler()
    elif control_ask == 4:
        RealTimeCrawler_obj.RealTimeDCinsideCrawler()

# 메인 함수 수정
def main():
    if len(sys.argv) < 5:
        print("사용법: RealTimeCRAWLER.py <crawler_type> <keyword> <speed> <check_page> [word_list_path]")
        sys.exit(1)

    crawler_type = sys.argv[1]  # 크롤러 유형
    keyword = sys.argv[2]       # 키워드
    speed = int(sys.argv[3])    # 속도
    check_page = int(sys.argv[4])  # 페이지 수

    # 추가 인수로 위험 단어 목록 경로 받기
    word_list_path = sys.argv[5] if len(sys.argv) == 6 else None

    # RealTimeCRAWLER 객체 생성 및 크롤링 시작
    crawler = RealTimeCRAWLER(keyword, speed=speed, checkPage=check_page, word_list_path=word_list_path)

    # 크롤러 유형에 따라 올바른 메서드 호출
    if crawler_type == "NaverCafe":
        crawler.RealTimeNaverCafeCrawler()
    elif crawler_type == "NaverBlog":
        crawler.RealTimeNaverBlogCrawler()
    elif crawler_type == "NaverNews":
        crawler.RealTimeNaverNewsCrawler()
    elif crawler_type == "DCinside":
        crawler.RealTimeDCinsideCrawler()
    else:
        print(f"잘못된 크롤러 유형: {crawler_type}")
        sys.exit(1)

if __name__ == '__main__':
    main()


if __name__ == '__main__':
    main()