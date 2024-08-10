import os
import sys

CRAWLER_PATH = os.path.dirname(os.path.abspath(__file__))
BIGMACLAB_PATH      = os.path.dirname(CRAWLER_PATH)
MANAGER_PATH        = os.path.join(BIGMACLAB_PATH, 'MANAGER')
sys.path.append(MANAGER_PATH)

import time
import asyncio
import warnings
import os
import re
from kiwipiepy import Kiwi
from datetime import datetime, timedelta

import shutil
import urllib3
from Package.CrawlerModule import CrawlerModule
from Package.GoogleModule import GoogleModule

from Package.ChinaCrawlerPackage.ChinaDailyCrawlerModule import ChinaDailyCrawler
from Package.ChinaCrawlerPackage.ChinaSinaCrawlerModule import ChinaSinaCrawler
from Package.NaverCrawlerPackage.NaverBlogCrawlerModule import NaverBlogCrawler
from Package.NaverCrawlerPackage.NaverCafeCrawlerModule import NaverCafeCrawler
from Package.NaverCrawlerPackage.NaverNewsCrawlerModule import NaverNewsCrawler
from Package.OtherCrawlerPackage.YouTubeCrawlerModule import YouTubeCrawler

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

class Crawler(CrawlerModule):
    
    def __init__(self, user, startDate, endDate, keyword, upload, speed, weboption):
        super().__init__(proxy_option=True)

        if user == '문요준':
            user = 'admin'

        self.running = True
        self.speed = int(speed)
        self.saveInterval = 90
        self.GooglePackage_obj = GoogleModule(self.pathFinder()['token_path'])
        self.kiwi = Kiwi(num_workers=8)

        # Computer Info
        self.scrapdata_path = self.pathFinder(user)['scrapdata_path']
        self.crawllog_path  = os.path.join(self.pathFinder()['crawler_folder_path'], 'CrawlLog')
        self.crawlcom       = self.pathFinder(user)['computer_name']
        self.mySQL          = self.pathFinder(user)['MYSQL']
        
        # User Info
        self.user      = user

        userData = self.get_userInfo(user, self.mySQL)
        self.userEmail = userData['Email']
        self.pushoverKey = userData['PushOver']

        # For Web Version
        self.weboption = int(weboption)
        
        self.startTime = time.time()
        self.now       = datetime.now()

        self.startDate = startDate
        self.endDate   = endDate
        self.keyword   = keyword
        self.DBkeyword = keyword.replace('"', "").replace(" ", "")
        self.upload    = upload
        
        self.startDate_form = datetime.strptime(startDate, '%Y%m%d').date()
        self.endDate_form   = datetime.strptime(endDate, '%Y%m%d').date()
        
        self.currentDate = self.startDate_form
        self.date_range  = (self.endDate_form - self.startDate_form).days + 1
        self.deltaD      = timedelta(days=1)

    # DB에 크롤링 상태 기록
    def DBinfoRecorder(self, endoption = False, error = False):
        option = self.option
        starttime = datetime.fromtimestamp(self.startTime).strftime('%m/%d %H:%M')
        endtime = '-'
        if error == True:
            endtime = 'ip 오류 중단'
        elif endoption == True:
            endtime = datetime.fromtimestamp(time.time()).strftime('%m/%d %H:%M')
        user = self.user
        self.mySQL.connectDB(self.DBname)
        self.mySQL.insertToTable(self.DBname + '_info', [option, starttime, endtime, user])
        self.mySQL.commit()

    # 크롤링 중단 검사
    def webCrawlerRunCheck(self):
        if self.DBname in self.mySQL.showAllDB():
            self.running = True
        else:
            print('\rStopped by BIGMACLAB MANAGER PROGRAM', end='')

            log = open(os.path.join(self.crawllog_path, self.DBname + '_log.txt'), 'w+')
            log.write(f"\n\n{datetime.fromtimestamp(self.startTime).strftime('%m/%d %H:%M')}에 중단됨")
            log.close()

            self.localDBRemover()
            sys.exit()

    def DBMaker(self, DBtype):
        dbname_date = "_{}_{}".format(self.startDate, self.endDate)
        self.DBname      = f"{DBtype}_{self.DBkeyword}{dbname_date}_{self.now.strftime('%m%d_%H%M')}"
        self.DBpath      = os.path.join(self.scrapdata_path, self.DBname)

        self.mySQL.newDB(self.DBname)
        self.mySQL.newTable(self.DBname + '_info', ['option', 'start', 'end', 'requester'])
        self.DBinfoRecorder()

        self.articleDB    = self.DBname + '_article'
        self.statisticsDB = self.DBname + '_statistics'
        self.replyDB      = self.DBname + '_reply'
        self.rereplyDB    = self.DBname + '_rereply'
        
        try:
            os.mkdir(self.DBpath)
            log = open(os.path.join(self.crawllog_path, self.DBname + '_log.txt'),'w+')

            self.msg = (
                f"=======================================================================================================================================\n"
                f"{'User:':<15} {self.user}\n"
                f"{'Object:':<15} {self.DBtype}\n"
                f"{'Option:':<15} {self.option}\n"
                f"{'Keyword:':<15} {self.keyword}\n"
                f"{'Date Range:':<15} {self.startDate_form.strftime('%Y.%m.%d')} ~ {self.endDate_form.strftime('%Y.%m.%d')}\n"
                f"{'Crawl Start:':<15} {datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M')}\n"
                f"{'Computer:':<15} {self.crawlcom}\n"
                f"{'DB path:':<15} {self.DBpath}\n"
                f"{'Drive Upload:':<15} {self.upload}\n"
                f"{'Crawler Speed:':<15} {self.speed}\n"
                f"=======================================================================================================================================\n"
            )
            log.write(self.msg + '\n\n')
            log.close()
        except:
            print("ERROR: DB 폴더 생성 실패 --> 잠시 후 다시 시도하세요")
            sys.exit()

    def localDBRemover(self):
        shutil.rmtree(self.DBpath)

    def infoPrinter(self):
        print(self.msg)
      
    def ReturnChecker(self, value):
        if isinstance(value, dict) == True:
            first_key = list(value.keys())[0]
            if first_key == 'Error Code':
                err_msg_title = self.error_extractor(value['Error Code'])
                err_msg_content = value['Error Msg']
                err_target = value['Error Target']

                log = open(os.path.join(self.crawllog_path, self.DBname + '_log.txt'), 'a')
                msg = (
                    f"\n\nError Time: {datetime.now()}\n"
                    f"Error Type: {err_msg_title}\n"
                    f"Error Detail: {err_msg_content}\n"
                    f"Error Target: {err_target}\n\n\n"
                )
                log.write(msg)
                log.close()
                return False
            else:
                return True
    
    def FinalOperator(self):
        self.mySQL.connectDB(self.DBname)
        DBlist = [DB for DB in self.mySQL.showAllDB() if 'info' not in DB]
        for DB in DBlist:
            data_df = self.mySQL.TableToDataframe(DB)

            if 'reply' in DB or 'rereply' in DB:
                data_df = data_df.groupby('Article URL').agg({
                    'Reply Text': ' '.join,
                    'Reply Date': 'first'
                }).reset_index()

            token_df = self.tokenization(data_df)
            self.mySQL.DataframeToTable(token_df, 'token_'+DB)

        self.clear_screen()
        print('\r업로드 및 알림 전송 중...', end = '')
        
        title = '[크롤링 완료] ' + self.DBname

        starttime = datetime.fromtimestamp(self.startTime).strftime('%Y-%m-%d %H:%M')
        endtime   = datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M')
        crawltime = str(timedelta(seconds=int(time.time() - self.startTime)))

        text = f'\n크롤링 시작: {starttime}' + f'\n크롤링 종료: {endtime}' + f'\n소요시간: {crawltime}'
        if self.upload == True:
            driveURL = self.GooglePackage_obj.UploadFolder(self.DBpath)
            text += f'\n\n크롤링 데이터: {driveURL}'

        if self.pushoverKey == 'n':
            self.GooglePackage_obj.SendMail(self.userEmail, title, text)
        else:
            self.send_pushOver(msg=title + '\n' + text, user_key=self.pushoverKey)

        end_msg = (
            f"|| 크롤링 종료 | 시작: {starttime} "
            f"| 종료: {endtime} "
            f"| 소요시간: {crawltime} ||"
        )

        self.DBinfoRecorder(endoption=True)
        self.localDBRemover()

        log = open(os.path.join(self.crawllog_path, self.DBname + '_log.txt'), 'a')
        log.write('\n\n'+end_msg)
        log.close()

        self.clear_screen()

        if self.weboption == False:
            self.infoPrinter()
        print(f'{end_msg}')

    def tokenization(self, data):
        for column in data.columns.tolist():
            if 'Text' in column:
                textColumn_name = column

        text_list = list(data[textColumn_name])
        tokenized_data = []

        for index, text in enumerate(text_list):
            try:
                if not isinstance(text, str):
                    tokenized_data.append([])
                    continue  # 문자열이 아니면 넘어감

                text = re.sub(r'[^가-힣a-zA-Z\s]', '', text)
                tokens = self.kiwi.tokenize(text)
                tokenized_text = [token.form for token in tokens if token.tag in ('NNG', 'NNP')]

                # 리스트를 쉼표로 구분된 문자열로 변환
                tokenized_text_str = ", ".join(tokenized_text)
                tokenized_data.append(tokenized_text_str)

                progress_value = round((index + 1) / len(text_list) * 100, 1)
                print(f'\r{textColumn_name.split(' ')[0]} Tokenization Progress: {progress_value}%')
            except:
                tokenized_data.append([])

        data[textColumn_name] = tokenized_data
        return data

    def Naver_News_Crawler(self, option):

        NaverNewsCrawler_obj = NaverNewsCrawler(proxy_option=True, print_status_option=True)
        NaverNewsCrawler_obj.setCrawlSpeed(self.speed)

        self.option = option
        self.DBtype = "navernews"
        self.DBMaker(self.DBtype)

        # initial list
        self.urlList         = []

        article_column     = ["Article Press", "Article Type", "Article URL", "Article Title", "Article Text", "Article Date", "Article ReplyCnt"]
        statistiscs_column = ["Article Press", "Article Type", "Article URL", "Article Title", "Article Text", "Article Date", "Article ReplyCnt", "Male", "Female", "10Y", "20Y", "30Y", "40Y", "50Y", "60Y"]
        reply_column       = ["Reply Num", "Reply Writer", "Reply Date", "Reply Text", "Rereply Count", "Reply Like", "Reply Bad", "Reply LikeRatio", 'Reply Sentiment', 'Article URL', 'Reply ID']
        rereply_column     = ["Reply_ID", "Rereply Writer", "Rereply Date", "Rereply Text", "Rereply Like", "Rereply Bad", "Rereply LikeRatio", "Rereply Sentiment", "Article URL"]

        self.mySQL.newTable(tableName=self.articleDB, column_list=article_column)
        self.mySQL.newTable(tableName=self.statisticsDB, column_list=statistiscs_column)
        self.mySQL.newTable(tableName=self.replyDB, column_list=reply_column)
        if option == 2:
            self.mySQL.newTable(tableName=self.rereplyDB, column_list=rereply_column)

        if self.weboption == 0:
            self.infoPrinter()

        while self.running == True:
            for dayCount in range(self.date_range + 1):
                try:
                    self.currentDate_str = self.currentDate.strftime('%Y%m%d')
                    percent = str(round(((dayCount+1)/self.date_range)*100, 1))
                    NaverNewsCrawler_obj.setPrintData(self.currentDate.strftime('%Y.%m.%d'), percent, self.weboption)

                    if dayCount % self.saveInterval == 0 or dayCount == self.date_range:

                        self.mySQL.TableToCSV(tableName=self.articleDB, csv_path=self.DBpath)
                        self.mySQL.TableToCSV(tableName=self.statisticsDB, csv_path=self.DBpath)
                        self.mySQL.TableToCSV(tableName=self.replyDB, csv_path=self.DBpath)
                        if option == 2:
                            self.mySQL.TableToCSV(tableName=self.rereplyDB, csv_path=self.DBpath)

                    # finish line
                    if dayCount == self.date_range:
                        self.FinalOperator()
                        return

                    # News URL Part
                    urlList_returnData = NaverNewsCrawler_obj.urlCollector(keyword=self.keyword, startDate=self.currentDate_str, endDate=self.currentDate_str)
                    if self.ReturnChecker(urlList_returnData) == False:
                        if dayCount == 0:
                            self.DBinfoRecorder(False, True)
                            self.localDBRemover()
                            os._exit(1)
                        continue
                    self.urlList = urlList_returnData['urlList']

                    FullreturnData = asyncio.run(NaverNewsCrawler_obj.asyncMultiCollector(self.urlList, option))

                    for returnData in FullreturnData:

                        # articleData 정상 확인
                        articleStatus = False
                        article_returnData = returnData['articleData']
                        if self.ReturnChecker(article_returnData) == True:
                            articleStatus = True

                        replyList_returnData = returnData['replyData']
                        # replyData 정상 확인
                        if self.ReturnChecker(replyList_returnData) == True:
                            if articleStatus == True and article_returnData['articleData'] != []:
                                self.mySQL.insertToTable(tableName=self.articleDB, data_list=article_returnData['articleData'] + [replyList_returnData['replyCnt']])

                                if replyList_returnData['statisticsData'] != []:
                                    self.mySQL.insertToTable(tableName=self.statisticsDB, data_list=article_returnData['articleData'] + replyList_returnData['statisticsData'])

                            if replyList_returnData['replyList'] != []:
                                self.mySQL.insertToTable(tableName=self.replyDB, data_list=replyList_returnData['replyList'])

                        if option == 2:
                            # rereplyData 정상확인
                            rereplyList_returnData = returnData['rereplyData']
                            if self.ReturnChecker(rereplyList_returnData) == True and rereplyList_returnData['rereplyList'] != []:
                                self.mySQL.insertToTable(tableName=self.rereplyDB, data_list=rereplyList_returnData['rereplyList'])

                    self.webCrawlerRunCheck()
                    self.mySQL.commit()
                    self.currentDate += self.deltaD

                except Exception as e:
                    error_msg = self.error_detector()
                    error_data = self.error_dump(1002, error_msg, self.currentDate_str)
                    self.ReturnChecker(error_data)
            return
    
    def Naver_Blog_Crawler(self, option):
        
        NaverBlogCrawler_obj = NaverBlogCrawler(proxy_option=True, print_status_option=True)
        NaverBlogCrawler_obj.setCrawlSpeed(self.speed)

        self.option = option
        self.DBtype = "naverblog"
        self.DBMaker(self.DBtype)
        
        # initial list
        self.urlList         = []

        article_column = ["Article ID", "Article URL", "Article Text", "Article Date"]
        reply_column   = ["Reply Num", "Reply Writer", "Reply Date", "Reply Text", "Rereply Count", "Reply Like", "Reply Bad", "Reply LikeRatio", 'Reply Sentiment', 'Article URL', 'Reply ID']

        self.mySQL.newTable(tableName=self.articleDB, column_list=article_column)
        if option == 2:
            self.mySQL.newTable(tableName=self.replyDB, column_list=reply_column)

        if self.weboption == 0:
            self.infoPrinter()

        while self.running == True:
            for dayCount in range(self.date_range + 1):
                try:
                    self.currentDate_str = self.currentDate.strftime('%Y%m%d')
                    percent = str(round(((dayCount+1)/self.date_range)*100, 1))
                    NaverBlogCrawler_obj.setPrintData(self.currentDate.strftime('%Y.%m.%d'), percent, self.weboption)

                    if dayCount % self.saveInterval == 0 or dayCount == self.date_range:
                        self.mySQL.TableToCSV(tableName=self.articleDB, csv_path=self.DBpath)
                        if option == 2:
                            self.mySQL.TableToCSV(tableName=self.replyDB, csv_path=self.DBpath)

                    # finish line
                    if dayCount == self.date_range:
                        self.FinalOperator()
                        return

                    # Blog Url Part
                    urlList_returnData = NaverBlogCrawler_obj.urlCollector(keyword=self.keyword, startDate=self.currentDate_str, endDate=self.currentDate_str)
                    if self.ReturnChecker(urlList_returnData) == False:
                        if dayCount == 0:
                            self.DBinfoRecorder(False, True)
                            self.localDBRemover()
                            os._exit(1)
                        continue

                    self.urlList = urlList_returnData['urlList']

                    FullreturnData = asyncio.run(NaverBlogCrawler_obj.asyncMultiCollector(self.urlList, option))

                    for returnData in FullreturnData:

                        article_returnData = returnData['articleData']
                        if self.ReturnChecker(article_returnData) == True and article_returnData['articleData'] != []:
                            self.mySQL.insertToTable(tableName=self.articleDB, data_list=article_returnData['articleData'])

                        if option == 2:
                            replyList_returnData = returnData['replyData']
                            if self.ReturnChecker(replyList_returnData) == True and replyList_returnData['replyList'] != []:
                                self.mySQL.insertToTable(tableName=self.replyDB, data_list=replyList_returnData['replyList'])

                    self.webCrawlerRunCheck()
                    self.mySQL.commit()
                    self.currentDate += self.deltaD

                except Exception as e:
                    error_msg = self.error_detector()
                    error_data = self.error_dump(1002, error_msg, self.currentDate_str)
                    self.ReturnChecker(error_data)
            return

    def Naver_Cafe_Crawler(self, option):
        
        NaverCafeCrawler_obj = NaverCafeCrawler(proxy_option=True, print_status_option=True)
        NaverCafeCrawler_obj.setCrawlSpeed(self.speed)

        self.option = option
        self.DBtype = "navercafe"
        self.DBMaker(self.DBtype)
        
        # initial list
        self.urlList         = []

        article_column = ["NaverCafe Name", "NaverCafe MemberCount", "Article Writer", "Article Title", "Article Text", "Article Date", "Article ReadCount", "Article ReplyCount", "Article URL"]
        reply_column   = ["Reply Num", "Reply Writer", "Reply Date", 'Reply Text', 'Article URL']

        self.mySQL.newTable(tableName=self.articleDB, column_list=article_column)
        if option == 2:
            self.mySQL.newTable(tableName=self.replyDB, column_list=reply_column)

        if self.weboption == 0:
            self.infoPrinter()

        while self.running == True:
            for dayCount in range(self.date_range + 1):
                try:
                    self.currentDate_str = self.currentDate.strftime('%Y%m%d')
                    percent = str(round(((dayCount+1)/self.date_range)*100, 1))
                    NaverCafeCrawler_obj.setPrintData(self.currentDate.strftime('%Y.%m.%d'), percent, self.weboption)

                    if dayCount % self.saveInterval == 0 or dayCount == self.date_range:
                        self.mySQL.TableToCSV(tableName=self.articleDB, csv_path=self.DBpath)
                        if option == 2:
                            self.mySQL.TableToCSV(tableName=self.replyDB, csv_path=self.DBpath)

                    # finish line
                    if dayCount == self.date_range:
                        self.FinalOperator()
                        return

                    # Cafe URL Part
                    urlList_returnData = NaverCafeCrawler_obj.urlCollector(keyword=self.keyword, startDate=self.currentDate_str, endDate=self.currentDate_str)
                    if self.ReturnChecker(urlList_returnData) == False:
                        if dayCount == 0:
                            self.DBinfoRecorder(False, True)
                            self.localDBRemover()
                            os._exit(1)
                        continue

                    self.urlList = urlList_returnData['urlList']

                    FullreturnData = asyncio.run(NaverCafeCrawler_obj.asyncMultiCollector(self.urlList, option))

                    for returnData in FullreturnData:

                        article_returnData = returnData['articleData']
                        if self.ReturnChecker(article_returnData) == True and article_returnData['articleData'] != []:
                            self.mySQL.insertToTable(tableName=self.articleDB, data_list=article_returnData['articleData'])

                        if option == 2:
                            replyList_returnData = returnData['replyData']
                            if self.ReturnChecker(replyList_returnData) == True and replyList_returnData['replyList'] != []:
                                self.mySQL.insertToTable(tableName=self.replyDB, data_list=replyList_returnData['replyList'])

                    self.webCrawlerRunCheck()
                    self.mySQL.commit()
                    self.currentDate += self.deltaD

                except Exception as e:
                    error_msg = self.error_detector()
                    error_data = self.error_dump(1002, error_msg, self.currentDate_str)
                    self.ReturnChecker(error_data)
            return

    def YouTube_Crawler(self, option):

        self.mySQL.connectDB('user_db')
        api_list_df = self.mySQL.TableToDataframe('youtube_api')
        api_list = api_list_df['API code'].tolist()

        YouTubeCrawler_obj = YouTubeCrawler(api_list=api_list, proxy_option=True, print_status_option=True)
        
        self.option = option
        self.DBtype = "youtube"
        self.DBMaker(self.DBtype)
        self.api_num = 1
        
        self.urlList = []

        article_column = ['YouTube Channel', 'Article URL', 'Article Title', 'Article Text', 'Article Date', 'Article ViewCount', 'Article Like', 'Article ReplyCount']
        reply_column = ['Reply Num', 'Reply Writer', 'Reply Date', 'Reply Text', 'Reply Like', 'Article URL']
        rereply_column = ['Rereply Num', 'Rereply Writer', 'Rereply Date', 'Rereply Text', 'Rereply Like', 'Article URL']

        self.mySQL.newTable(tableName=self.articleDB, column_list=article_column)
        self.mySQL.newTable(tableName=self.replyDB, column_list=reply_column)
        self.mySQL.newTable(tableName=self.rereplyDB, column_list=rereply_column)

        if self.weboption == 0:
            self.infoPrinter()

        while self.running == True:
            for dayCount in range(self.date_range + 1):
                try:
                    self.currentDate_str = self.currentDate.strftime('%Y%m%d')
                    percent = str(round(((dayCount+1)/self.date_range)*100, 1))
                    YouTubeCrawler_obj.setPrintData(self.currentDate.strftime('%Y.%m.%d'), percent, self.weboption, self.api_num)

                    if dayCount % self.saveInterval == 0 or dayCount == self.date_range:
                        # option 1 & 2
                        self.mySQL.TableToCSV(tableName=self.articleDB, csv_path=self.DBpath)
                        self.mySQL.TableToCSV(tableName=self.replyDB, csv_path=self.DBpath)
                        self.mySQL.TableToCSV(tableName=self.rereplyDB, csv_path=self.DBpath)

                    # finish line
                    if dayCount == self.date_range:
                        self.FinalOperator()
                        return

                    # YouTube URL Part
                    urlList_returnData = YouTubeCrawler_obj.urlCollector(keyword=self.keyword, startDate=self.currentDate_str, endDate=self.currentDate_str)
                    if self.ReturnChecker(urlList_returnData) == False:
                        if dayCount == 0:
                            self.DBinfoRecorder(False, True)
                            self.localDBRemover()
                            os._exit(1)
                        continue

                    self.urlList = urlList_returnData['urlList']

                    FullreturnData = YouTubeCrawler_obj.syncMultiCollector(self.urlList, option)

                    for returnData in FullreturnData:

                        article_returnData = returnData['articleData']
                        if self.ReturnChecker(article_returnData) == True and article_returnData['articleData'] != []:
                            self.mySQL.insertToTable(tableName=self.articleDB, data_list=article_returnData['articleData'])

                        replyList_returnData = returnData['replyData']
                        if self.ReturnChecker(replyList_returnData) == True:
                            if replyList_returnData['replyList'] != []:
                                self.mySQL.insertToTable(tableName=self.replyDB, data_list=replyList_returnData['replyList'])
                            if replyList_returnData['rereplyList'] != []:
                                self.mySQL.insertToTable(tableName=self.rereplyDB, data_list=replyList_returnData['rereplyList'])

                    self.webCrawlerRunCheck()
                    self.mySQL.commit()
                    self.currentDate += self.deltaD

                except Exception as e:
                    error_msg = self.error_detector()
                    error_data = self.error_dump(1002, error_msg, self.currentDate_str)
                    self.ReturnChecker(error_data)
            return

    def ChinaDaily_Crawler(self, option):
        
        ChinaDailyCrawler_obj = ChinaDailyCrawler(proxy_option=True, print_status_option=True)
        
        self.option = option
        self.DBtype = "chinadaily"
        self.DBMaker(self.DBtype)
        
        article_column = ['Article Source', 'Article Title', 'Article Text', 'Article Date', 'Article Theme', 'Article URL', 'Article SearchURL']
        self.mySQL.newTable(tableName=self.articleDB, column_list=article_column)

        if self.weboption == 0:
            self.infoPrinter()

        while self.running == True:
            for dayCount in range(self.date_range + 1):
                try:
                    self.currentDate_str = self.currentDate.strftime('%Y%m%d')
                    percent = str(round(((dayCount+1)/self.date_range)*100, 1))
                    ChinaDailyCrawler_obj.setPrintData(self.currentDate.strftime('%Y.%m.%d'), percent, self.weboption)

                    if dayCount % self.saveInterval == 0 or dayCount == self.date_range:
                        # option 1 & 2
                        self.mySQL.TableToCSV(tableName=self.articleDB, csv_path=self.DBpath)

                    # finish line
                    if dayCount == self.date_range:
                        self.FinalOperator()
                        return

                    articleList_returnData = ChinaDailyCrawler_obj.articleCollector(keyword=self.keyword, startDate=self.currentDate_str, endDate=self.currentDate_str)
                    if self.ReturnChecker(articleList_returnData) == False:
                        continue
                    articleList = articleList_returnData['articleList']
                    articleCnt  = articleList_returnData['articleCnt']

                    if articleCnt != 0:
                        self.mySQL.TableToCSV(tableName=self.articleDB, csv_path=self.DBpath)

                    self.webCrawlerRunCheck()
                    self.mySQL.commit()
                    self.currentDate += self.deltaD

                except Exception as e:
                    error_msg = self.error_detector()
                    error_data = self.error_dump(1002, error_msg, self.currentDate_str)
                    self.ReturnChecker(error_data)
            return

    def ChinaSina_Crawler(self, option):
        
        ChinaSinaCrawler_obj = ChinaSinaCrawler(proxy_option=True, print_status_option=True)
        ChinaSinaCrawler_obj.setCrawlSpeed(self.speed)
        
        self.option = option
        self.DBtype = "chinasina"
        self.DBMaker(self.DBtype)
        

        article_column = ['Article Title', 'Article Text', 'Article Date', 'Article URL']
        reply_column = ['Reply Num', 'Reply Writer', 'Reply Date', 'Reply Text', 'Reply Like', 'Article URL']

        self.mySQL.newTable(tableName=self.articleDB, column_list=article_column)
        if option == 2:
            self.mySQL.newTable(tableName=self.replyDB, column_list=reply_column)

        if self.weboption == 0:
            self.infoPrinter()
        
        DateRangeList = ChinaSinaCrawler_obj.DateSplitter(self.startDate, self.endDate)
        DateRangeList.append(DateRangeList[-1])
        DateRangeCnt  = 0

        while self.running == True:
            for DateRange in DateRangeList:
                try:
                    articleList = []
                    DateRangeCnt += 1
                    currentDate_start = DateRange[0]
                    currentDate_end   = DateRange[1]
                    currentDate_str_start = datetime.strptime(DateRange[0], '%Y%m%d').date()
                    currentDate_str_end   = datetime.strptime(DateRange[1], '%Y%m%d').date()
                    percent = str(round(((DateRangeCnt+1)/len(DateRangeList))*100, 1))

                    ChinaSinaCrawler_obj.setPrintData(f"{currentDate_str_start.strftime('%Y.%m.%d')} ~ {currentDate_str_end.strftime('%Y.%m.%d')}", percent, self.weboption)

                    self.mySQL.TableToCSV(tableName=self.articleDB, csv_path=self.DBpath)
                    if option == 2:
                        self.mySQL.TableToCSV(tableName=self.replyDB, csv_path=self.DBpath)

                    if DateRangeCnt == len(DateRangeList):
                        self.FinalOperator()
                        return

                    urlList_returnData = ChinaSinaCrawler_obj.urlCollector(keyword=self.keyword, startDate=currentDate_start, endDate=currentDate_end)
                    if self.ReturnChecker(urlList_returnData) == False:
                        if DateRange == DateRangeList[0]:
                            self.DBinfoRecorder(False, True)
                            self.localDBRemover()
                            os._exit(1)
                        continue
                    self.urlList = urlList_returnData['urlList']

                    FullreturnData = asyncio.run(ChinaSinaCrawler_obj.asyncMultiCollector(self.urlList, option))

                    for returnData in FullreturnData:

                        article_returnData = returnData['articleData']
                        if self.ReturnChecker(article_returnData) == True and article_returnData['articleData'] != 0:
                            articleList.append(article_returnData['articleData'])

                        if option == 2:
                            replyList_returnData = returnData['replyData']
                            if self.ReturnChecker(replyList_returnData) == True and replyList_returnData['replyList'] != []:
                                self.mySQL.insertToTable(tableName=self.replyDB, data_list=replyList_returnData['replyList'])

                    self.mySQL.insertToTable(tableName=self.articleDB, data_list=sorted(articleList, key=lambda x: datetime.strptime(x[2], "%Y-%m-%d")))

                    self.webCrawlerRunCheck()
                    self.mySQL.commit()

                except Exception as e:
                    error_msg = self.error_detector()
                    error_data = self.error_dump(1002, error_msg, self.currentDate_str)
                    self.ReturnChecker(error_data)
            return

def controller():
    option_dic = {
        1 : "\n1. 기사 + 댓글\n2. 기사 + 댓글/대댓글\n",
        2 : "\n1. 블로그 본문\n2. 블로그 본문 + 댓글/대댓글\n",
        3 : "\n1. 카페 본문\n2. 카페 본문 + 댓글/대댓글\n",
        4 : "\n1. 영상 정보 + 댓글/대댓글 (100개 제한)\n2. 영상 정보 + 댓글/대댓글(무제한)\n",
        5 : "\n1. 기사\n",
        6 : "\n1. 기사\n2. 기사 + 댓글\n"
    }
    print("================ Crawler Controller ================")
    name = input("본인의 이름을 입력하세요: ")
    
    print("\n[ 크롤링 대상 ]\n")
    print("1. Naver News\n2. Naver Blog\n3. Naver Cafe\n4. YouTube\n5. ChinaDaily\n6. ChinaSina")
    
    while True:
        control_ask = int(input("\n입력: "))
        if control_ask in [1,2,3,4,5,6]:
            break
        else:
            print("다시 입력하세요")
    

    startDate = input("\nStart Date (ex: 20230101): ") 
    endDate   = input("End Date (ex: 20231231): ") 
    keyword   = input("\nKeyword: ")
    
    print(option_dic[control_ask])
    
    while True:
        option = int(input("Option: "))
        if option in [1,2]:
            break
        else:
            print("다시 입력하세요")
            
    upload    = input("\n메일로 크롤링 데이터를 받으시겠습니까(1/0)? ")
    speed     = input("\n속도를 입력하십시오(1~10):  ")
    weboption = 0

    Crawler_obj = Crawler(name, startDate, endDate, keyword, upload, speed, weboption)
    Crawler_obj.clear_screen()
    
    if control_ask == 1:
        Crawler_obj.Naver_News_Crawler(option)
    
    elif control_ask == 2:
        Crawler_obj.Naver_Blog_Crawler(option)
        
    elif control_ask == 3:
        Crawler_obj.Naver_Cafe_Crawler(option)
        
    elif control_ask == 4:
        Crawler_obj.YouTube_Crawler(option)
    
    elif control_ask == 5:
        Crawler_obj.ChinaDaily_Crawler(option)
        
    elif control_ask == 6:
        Crawler_obj.ChinaSina_Crawler(option)

if __name__ == '__main__':
    controller()
    
    