from Package.OtherCrawlerPackage.YouTubeCrawlerModule import YouTubeCrawler
from Package.NaverCrawlerPackage.NaverNewsCrawlerModule import NaverNewsCrawler
from Package.NaverCrawlerPackage.NaverCafeCrawlerModule import NaverCafeCrawler
from Package.NaverCrawlerPackage.NaverBlogCrawlerModule import NaverBlogCrawler
from Package.ChinaCrawlerPackage.ChinaSinaCrawlerModule import ChinaSinaCrawler
from Package.ChinaCrawlerPackage.ChinaDailyCrawlerModule import ChinaDailyCrawler
from dotenv import load_dotenv
import pandas as pd
from Package.GoogleModule import GoogleModule
from Package.CrawlerModule import CrawlerModule
import urllib3
import shutil
from datetime import datetime, timedelta, timezone
import requests
from kiwipiepy import Kiwi
import socket
import re
import warnings
import asyncio
import traceback
import time
import os
import sys

CRAWLER_PATH = os.path.dirname(os.path.abspath(__file__))
BIGMACLAB_PATH = os.path.dirname(CRAWLER_PATH)
MANAGER_PATH = os.path.join(BIGMACLAB_PATH, 'MANAGER')
sys.path.append(MANAGER_PATH)


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

load_dotenv()


class Crawler(CrawlerModule):

    def __init__(self, user, startDate, endDate, keyword, upload, speed, weboption):
        self.proxy_option = True
        if socket.gethostname() == "Yojuns-MacBook-Pro.local":
            self.proxy_option = False
        super().__init__(proxy_option=self.proxy_option)

        if user == '문요준':
            user = 'admin'

        self.running = True
        self.speed = int(speed)
        self.saveInterval = 90
        self.GooglePackage_obj = GoogleModule(self.pathFinder()['token_path'])
        self.admin_pushoverkey = 'uvz7oczixno7daxvgxmq65g2gbnsd5'

        # Computer Info
        self.scrapdata_path = self.pathFinder()['scrapdata_path']
        self.crawllog_path = os.path.join(
            self.pathFinder()['crawler_folder_path'], 'crawllog')
        self.crawlcom = self.pathFinder()['computer_name']
        self.api_url = "http://localhost:8000/api"
        #self.api_url = "https://manager.knpu.re.kr/api"
        self.api_headers = {
            "Authorization": "Bearer " + os.getenv('ADMIN_TOKEN'),
        }
        self.mongoDB()

        # User Info
        self.user = user

        userData = self.get_userInfo(user)
        if not userData:
            print("등록되지 않은 사용자입니다. 크롤러를 종료합니다")
            os._exit(0)

        self.userEmail = userData['Email']
        self.pushoverKey = userData['PushOver']

        # For Web Version
        self.weboption = int(weboption)
        self.localArchive = False

        self.startTime = time.time()
        self.now = datetime.now()

        self.startDate = startDate
        self.endDate = endDate
        self.keyword = keyword
        self.DBkeyword = keyword

        replacements = {
            '\\': '＼',  # U+FF3C
            '/': '／',   # U+FF0F
            ':': '：',   # U+FF1A
            '*': '＊',   # U+FF0A
            '?': '？',   # U+FF1F
            '"': '＂',   # U+FF02
            '<': '＜',   # U+FF1C
            '>': '＞',   # U+FF1E
            '|': '¦',    # U+00A6
        }

        # 3) 매핑 테이블을 이용해 한 번에 replace
        for illegal, safe in replacements.items():
            self.DBkeyword = self.DBkeyword.replace(illegal, safe)
        
        self.upload = upload

        self.startDate_form = datetime.strptime(startDate, '%Y%m%d').date()
        self.endDate_form = datetime.strptime(endDate, '%Y%m%d').date()

        self.currentDate = self.startDate_form
        self.date_range = (self.endDate_form - self.startDate_form).days + 1
        self.deltaD = timedelta(days=1)

    # DB에 크롤링 상태 기록
    def DBinfoRecorder(self, endoption=False, error=False):

        if error == True:
            requests.put(f"{self.api_url}/crawls/{self.dbUid}/error", headers=self.api_headers).json()

        elif endoption == True:
            del self.IntegratedDB['UrlCnt']
            requests.put(f"{self.api_url}/crawls/{self.dbUid}/end", headers=self.api_headers).json()
            with open(os.path.join(self.crawllog_path, self.DBname + '_log.txt'), 'r') as log:
                log_content = log.read()

            json = {
                'uid': self.dbUid,
                'content': log_content
            }
            requests.post(f"{self.api_url}/crawls/add/log", json=json, headers=self.api_headers).json()

    # 크롤링 중단 검사
    def webCrawlerRunCheck(self):
        crawlDbList = self.mongoClient['crawler']['db-list']
        targetDB = crawlDbList.find_one({'uid': self.dbUid})

        if not targetDB:
            self.running = False
            print('\rStopped by MANAGER PROGRAM', end='')

            log = open(os.path.join(self.crawllog_path,
                       self.DBname + '_log.txt'), 'a')
            log.write(
                f"\n\nDB Check --> {datetime.fromtimestamp(self.startTime).strftime('%Y%m/%d %H:%M')}에 중단됨")
            log.close()

            msg_text = (
                "[ CRAWLER STOPPED ]\n\n"
                f"Object DB : {self.DBname}\n\n"
                f"DB 저장소 삭제 또는 인식 불가로 {self.DBname} 크롤링이 중단되었습니다\n"
                f"의도된 크롤링 중단이 아니라면 Admin에게 연락 부탁드립니다"
            )
            self.sendPushOver(msg_text, user_key=self.pushoverKey)

            self.localDBRemover()
            sys.exit()

    def DBMaker(self, DBtype):
        dbname_date = "_{}_{}".format(self.startDate, self.endDate)

        now_kst = datetime.now(timezone.utc).astimezone(
            timezone(timedelta(hours=9))
        ).strftime('%m%d_%H%M')

        self.DBname = f"{DBtype}_{self.DBkeyword}{dbname_date}_{now_kst}"
        self.DBpath = os.path.join(self.scrapdata_path, self.DBname)

        option = self.option
        requester = self.user
        keyword = self.keyword
        crawlcom = self.crawlcom
        crawlspeed = self.speed

        json = {
            "name": self.DBname,
            "crawlOption": option,
            "requester": requester,
            "keyword": keyword,
            "dbSize": 0,
            "crawlCom": crawlcom,
            "crawlSpeed": crawlspeed,
        }

        res = requests.post(self.api_url + '/crawls/add',
                            json=json, headers=self.api_headers).json()
        self.dbUid = res['data']['uid']

        self.articleDB = self.DBname + '_article'
        self.statisticsDB = self.DBname + '_statistics'
        self.replyDB = self.DBname + '_reply'
        self.rereplyDB = self.DBname + '_rereply'

        try:
            os.makedirs(self.DBpath)
            log = open(os.path.join(self.crawllog_path,
                       self.DBname + '_log.txt'), 'w+')

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
            print(traceback.format_exc())
            os._exit(0)

    def localDBRemover(self):
        if self.localArchive == True:
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

                log = open(os.path.join(self.crawllog_path,
                           self.DBname + '_log.txt'), 'a')
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
        try:
            self.convertToParquet(self.DBpath)

            parquet_files = [f for f in os.listdir(
                self.DBpath) if f.endswith('.parquet')]
            for file_name in parquet_files:
                table_name = file_name.rsplit('.', 1)[0]
                file_path = os.path.join(self.DBpath, file_name)
                print(f"{table_name} 읽는 중...")

                data_df = pd.read_parquet(file_path)

                # Step 3: Reply 관련 테이블이면 전처리 수행
                # 전처리 부분 수정 예시
                if 'reply' in table_name or 'rereply' in table_name:
                    date_column = 'Rereply Date' if 'rereply' in table_name else 'Reply Date'
                    text_column = 'Rereply Text' if 'rereply' in table_name else 'Reply Text'

                    data_df[date_column] = pd.to_datetime(
                        data_df[date_column], errors='coerce').dt.date

                    # 결측치를 빈 문자열로 치환
                    data_df[text_column] = data_df[text_column].fillna('')

                    grouped = data_df.groupby('Article URL')
                    data_df = grouped.agg({
                        text_column: lambda x: ' '.join(x),
                        'Article Day': 'first'
                    }).reset_index()

                    data_df = data_df.rename(
                        columns={'Article Day': date_column})
                    data_df = data_df.sort_values(by=date_column)


                # Step 4: Tokenization
                token_df = self.tokenization(data_df)

                # Step 5: 저장 (선택 사항: parquet 저장 or print only)
                for col in token_df.columns:
                    if token_df[col].apply(lambda x: isinstance(x, list)).any():
                        token_df[col] = token_df[col].apply(lambda x: ' '.join(
                            map(str, x)) if isinstance(x, list) else x)

                token_file_path = os.path.join(
                    self.DBpath, f"token_{table_name}.parquet")
                token_df.to_parquet(token_file_path, index=False)
                print(f"Token 저장 완료: token_{table_name}.parquet")

            self.clear_screen()
            print('\r업로드 및 알림 전송 중...', end='')

            title = '[크롤링 완료] ' + self.DBname

            starttime = datetime.fromtimestamp(
                self.startTime).strftime('%Y-%m-%d %H:%M')
            endtime = datetime.fromtimestamp(
                time.time()).strftime('%Y-%m-%d %H:%M')
            crawltime = str(
                timedelta(seconds=int(time.time() - self.startTime)))

            text = f'\n크롤링 시작: {starttime}' + \
                f'\n크롤링 종료: {endtime}' + f'\n소요시간: {crawltime}'
            text += f'\n\nArticle: {self.IntegratedDB['totalArticleCnt']}' + \
                f'\nReply: {self.IntegratedDB['totalReplyCnt']}' + \
                f'\nRereply: {self.IntegratedDB['totalRereplyCnt']}'

            if self.upload == True:
                driveURL = self.GooglePackage_obj.UploadFolder(self.DBpath)
                text += f'\n\n크롤링 데이터: {driveURL}'

            if self.pushoverKey == 'n':
                self.GooglePackage_obj.SendMail(self.userEmail, title, text)
            else:
                self.sendPushOver(msg=title + '\n' + text,
                                  user_key=self.pushoverKey)

            end_msg = (
                f"|| 크롤링 종료 | 시작: {starttime} "
                f"| 종료: {endtime} "
                f"| 소요시간: {crawltime} ||"
            )

            with open(os.path.join(self.crawllog_path, self.DBname + '_log.txt'), 'a') as log:
                log.write('\n\n' + end_msg)

            self.DBinfoRecorder(endoption=True)

            self.clear_screen()

            if self.weboption == False:
                self.infoPrinter()
            print(f'{end_msg}')
        except:
            error_msg = self.error_detector()
            error_data = self.error_dump(1002, error_msg, self.currentDate_str)
            self.ReturnChecker(error_data)

    def tokenization(self, data):
        kiwi = Kiwi(num_workers=-1)
        for column in data.columns.tolist():
            if 'Text' in column:
                textColumn_name = column

        text_list = list(data[textColumn_name])
        tokenized_data = []

        total_texts = len(text_list)
        total_time = 0  # 전체 소요시간 계산

        for index, text in enumerate(text_list):
            start_time = time.time()

            try:
                if not isinstance(text, str):
                    tokenized_data.append([])
                    continue

                # 한글, 영문, 공백만 남김
                text = re.sub(r'[^가-힣a-zA-Z\s]', '', text)

                # splitComplex=False로 복합어 분리하지 않고 형태소 분석
                tokens = kiwi.tokenize(text, split_complex=False)

                # NNG 또는 NNP 품사만 추출
                tokenized_text = [token.form for token in tokens if token.tag in ('NNG', 'NNP')]

                tokenized_text_str = ", ".join(tokenized_text)
                tokenized_data.append(tokenized_text_str)

            except Exception as e:
                tokenized_data.append([])

            end_time = time.time()
            total_time += end_time - start_time

            avg_time_per_text = total_time / (index + 1)
            remaining_time = avg_time_per_text * (total_texts - (index + 1))

            remaining_minutes = int(remaining_time // 60)
            remaining_seconds = int(remaining_time % 60)

            update_interval = 500
            if (index + 1) % update_interval == 0 or index + 1 == total_texts:
                progress_value = round((index + 1) / total_texts * 100, 2)
                print(
                    f'\r{textColumn_name.split(" ")[0]} Tokenization Progress: {progress_value}% | '
                    f'예상 남은 시간: {remaining_minutes}분 {remaining_seconds}초', end=''
                )

        data[textColumn_name] = tokenized_data
        return data


    def makeCSV(self, tableName, columns):
        df = pd.DataFrame(columns=columns)
        file_path = os.path.join(self.DBpath, tableName + '.csv')
        df.to_csv(file_path, index=False, encoding='utf-8-sig')

    def addToCSV(self, tableName, data_list, columns):
        df_new = pd.DataFrame(data_list, columns=columns)
        file_path = os.path.join(self.DBpath, f"{tableName}.csv")

        if not os.path.exists(file_path):
            self.running = False
            print('\rStopped by MANAGER PROGRAM', end='')

            log = open(os.path.join(self.crawllog_path,
                       self.DBname + '_log.txt'), 'a')
            log.write(
                f"\n\nDB Check --> {datetime.fromtimestamp(self.startTime).strftime('%Y%m/%d %H:%M')}에 중단됨")
            log.close()

            msg_text = (
                "[ CRAWLER STOPPED ]\n\n"
                f"Object DB : {self.DBname}\n\n"
                f"DB 저장소 삭제 또는 인식 불가로 {self.DBname} 크롤링이 중단되었습니다\n"
                f"의도된 크롤링 중단이 아니라면 Admin에게 연락 부탁드립니다"
            )
            self.sendPushOver(msg_text, user_key=self.pushoverKey)

            self.localDBRemover()
            sys.exit()

        write_header = not os.path.exists(file_path)
        df_new.to_csv(file_path, mode='a', header=write_header, index=False)

    def convertToParquet(self, folder_path):
        try:
            if not os.path.exists(folder_path):
                print(f"경로가 존재하지 않습니다: {folder_path}")
                return

            file_list = os.listdir(folder_path)
            csv_files = [f for f in file_list if f.lower().endswith('.csv')]

            if not csv_files:
                print("CSV 파일이 없습니다.")
                return

            for csv_file in csv_files:
                csv_path = os.path.join(folder_path, csv_file)
                parquet_path = os.path.join(
                    folder_path, csv_file.rsplit('.', 1)[0] + '.parquet')
                try:
                    df = pd.read_csv(csv_path)
                    df.to_parquet(parquet_path, index=False)
                    os.remove(csv_path)  # ✅ 변환 성공 후 원본 CSV 삭제
                except Exception as e:
                    print(f"변환 실패: {csv_file} → 오류: {e}")
        except Exception as e:
            error_msg = self.error_detector()
            error_data = self.error_dump(1002, error_msg, self.currentDate_str)
            self.ReturnChecker(error_data)

    def Naver_News_Crawler(self, option):

        NaverNewsCrawler_obj = NaverNewsCrawler(
            proxy_option=self.proxy_option, print_status_option=True)
        NaverNewsCrawler_obj.setCrawlSpeed(self.speed)

        self.option = option
        self.DBtype = "navernews"
        self.DBMaker(self.DBtype)

        # initial list
        self.urlList = []

        article_column = ["Article Press", "Article Type", "Article URL",
                          "Article Title", "Article Text", "Article Date", "Article ReplyCnt"]
        statistiscs_column = ["Article Press", "Article Type", "Article URL", "Article Title", "Article Text",
                              "Article Date", "Article ReplyCnt", "Male", "Female", "10Y", "20Y", "30Y", "40Y", "50Y", "60Y"]
        reply_column = ["Reply Num", "Reply Writer", "Reply Date", "Reply Text", "Rereply Count", "Reply Like",
                        "Reply Bad", "Reply LikeRatio", 'Reply Sentiment', 'Article URL', 'Reply ID', 'Article Day']
        rereply_column = ["Reply_ID", "Rereply Writer", "Rereply Date", "Rereply Text", "Rereply Like",
                          "Rereply Bad", "Rereply LikeRatio", "Rereply Sentiment", "Article URL", 'Article Day']

        if option == 4:
            reply_column = ["Reply Num", "Reply Writer", "Reply Date", "Reply Text", "Rereply Count", "Reply Like", "Reply Bad", "Reply LikeRatio",
                            'Reply Sentiment', 'Article URL', 'Reply ID', 'TotalUserComment', 'TotalUserReply', 'TotalUserLike', 'Article Day']

        self.makeCSV(tableName=self.articleDB, columns=article_column)

        if option in [1, 2, 4]:
            self.makeCSV(tableName=self.replyDB, columns=reply_column)
            self.makeCSV(tableName=self.statisticsDB, columns=statistiscs_column)
            if option == 2:
                self.makeCSV(tableName=self.rereplyDB, columns=rereply_column)

        if self.weboption == 0:
            self.infoPrinter()

        while self.running == True:
            for dayCount in range(self.date_range + 1):
                try:
                    self.currentDate_str = self.currentDate.strftime('%Y%m%d')
                    percent = str(
                        round(((dayCount + 1) / self.date_range) * 100, 1))
                    NaverNewsCrawler_obj.setPrintData(
                        self.currentDate.strftime('%Y.%m.%d'), percent, self.weboption)

                    # finish line
                    if dayCount == self.date_range:
                        self.FinalOperator()
                        return

                    # News URL Part
                    urlList_returnData = NaverNewsCrawler_obj.urlCollector(
                        keyword=self.keyword, startDate=self.currentDate_str, endDate=self.currentDate_str)
                    if self.ReturnChecker(urlList_returnData) == False:
                        if dayCount == 0:
                            msg_text = (
                                "[ CRAWLER STOPPED ]\n\n"
                                f"초기 데이터 수집 불가로 {self.DBname} 크롤링이 중단되었습니다\n\n"
                                f"IP Proxy 프로그램이 가동 중인지, IP가 최신 버전으로 업데이트되었는지 확인바랍니다\n"
                            )
                            self.sendPushOver(
                                msg_text, user_key=self.pushoverKey)
                            self.DBinfoRecorder(False, True)
                            self.localDBRemover()
                            os._exit(1)
                        self.currentDate += self.deltaD
                        continue

                    self.urlList = urlList_returnData['urlList']

                    FullreturnData = asyncio.run(
                        NaverNewsCrawler_obj.asyncMultiCollector(self.urlList, option))
                    for returnData in FullreturnData:
                        # articleData 정상 확인
                        articleStatus = False
                        article_returnData = returnData['articleData']
                        if self.ReturnChecker(article_returnData) == True and article_returnData['articleData'] != []:
                            articleStatus = True
                        else:
                            continue

                        if option == 3:
                            self.addToCSV(tableName=self.articleDB, data_list=[article_returnData['articleData'] + [0]], columns=article_column)

                        else:
                            replyList_returnData = returnData['replyData']
                            # replyData 정상 확인
                            if self.ReturnChecker(replyList_returnData) == True:
                                if articleStatus == True and article_returnData['articleData'] != []:
                                    self.addToCSV(tableName=self.articleDB, data_list=[
                                                  article_returnData['articleData'] + [replyList_returnData['replyCnt']]], columns=article_column)

                                    if replyList_returnData['statisticsData'] != []:
                                        self.addToCSV(tableName=self.statisticsDB, data_list=[
                                                      article_returnData['articleData'] + replyList_returnData['statisticsData']], columns=statistiscs_column)

                                if replyList_returnData['replyList'] != []:
                                    data_list = [sublist + [article_returnData['articleData'][5]]
                                                 for sublist in replyList_returnData['replyList']]
                                    self.addToCSV(
                                        tableName=self.replyDB, data_list=data_list, columns=reply_column)

                            if option == 2:
                                # rereplyData 정상확인
                                rereplyList_returnData = returnData['rereplyData']
                                if self.ReturnChecker(rereplyList_returnData) == True and rereplyList_returnData[
                                        'rereplyList'] != []:
                                    data_list = [sublist + [article_returnData['articleData'][5]] for sublist in
                                                 rereplyList_returnData['rereplyList']]
                                    self.addToCSV(
                                        tableName=self.rereplyDB, data_list=data_list, columns=rereply_column)

                    self.webCrawlerRunCheck()

                    self.currentDate += self.deltaD
                    self.IntegratedDB = NaverNewsCrawler_obj.CountReturn()
                    
                    res = requests.put(f"{self.api_url}/crawls/{self.dbUid}/count", json=self.IntegratedDB, headers=self.api_headers).json()

                except Exception as e:
                    error_msg = self.error_detector()
                    error_data = self.error_dump(
                        1002, error_msg, self.currentDate_str)
                    self.ReturnChecker(error_data)
            return

    def Naver_Blog_Crawler(self, option):

        NaverBlogCrawler_obj = NaverBlogCrawler(
            proxy_option=self.proxy_option, print_status_option=True)
        NaverBlogCrawler_obj.setCrawlSpeed(self.speed)

        self.option = option
        self.DBtype = "naverblog"
        self.DBMaker(self.DBtype)

        # initial list
        self.urlList = []

        article_column = ["Article ID", "Article URL",
                          "Article Text", "Article Date"]
        reply_column = ["Reply Num", "Reply Writer", "Reply Date", "Reply Text", "Rereply Count", "Reply Like",
                        "Reply Bad", "Reply LikeRatio", 'Reply Sentiment', 'Article URL', 'Reply ID', 'Article Day']

        self.makeCSV(tableName=self.articleDB, columns=article_column)
        if option == 2:
            self.makeCSV(tableName=self.replyDB, columns=reply_column)

        if self.weboption == 0:
            self.infoPrinter()

        while self.running == True:
            for dayCount in range(self.date_range + 1):
                try:
                    self.currentDate_str = self.currentDate.strftime('%Y%m%d')
                    percent = str(round(((dayCount+1)/self.date_range)*100, 1))
                    NaverBlogCrawler_obj.setPrintData(
                        self.currentDate.strftime('%Y.%m.%d'), percent, self.weboption)

                    # finish line
                    if dayCount == self.date_range:
                        self.FinalOperator()
                        return

                    # Blog Url Part
                    urlList_returnData = NaverBlogCrawler_obj.urlCollector(
                        keyword=self.keyword, startDate=self.currentDate_str, endDate=self.currentDate_str)
                    if self.ReturnChecker(urlList_returnData) == False:
                        if dayCount == 0:
                            msg_text = (
                                "[ CRAWLER STOPPED ]\n\n"
                                f"초기 데이터 수집 불가로 {self.DBname} 크롤링이 중단되었습니다\n\n"
                                f"IP Proxy 프로그램이 가동 중인지, IP가 최신 버전으로 업데이트되었는지 확인바랍니다\n"
                            )
                            self.sendPushOver(
                                msg_text, user_key=self.pushoverKey)
                            self.DBinfoRecorder(False, True)
                            self.localDBRemover()
                            os._exit(1)
                        self.currentDate += self.deltaD
                        continue

                    self.urlList = urlList_returnData['urlList']

                    FullreturnData = asyncio.run(
                        NaverBlogCrawler_obj.asyncMultiCollector(self.urlList, option))
                    for returnData in FullreturnData:

                        article_returnData = returnData['articleData']
                        if self.ReturnChecker(article_returnData) == True and article_returnData['articleData'] != []:
                            self.addToCSV(tableName=self.articleDB, data_list=[
                                          article_returnData['articleData']], columns=article_column)
                        else:
                            continue

                        if option == 2:
                            replyList_returnData = returnData['replyData']
                            if self.ReturnChecker(replyList_returnData) == True and replyList_returnData['replyList'] != []:
                                data_list = [sublist + [article_returnData['articleData'][3]]
                                             for sublist in replyList_returnData['replyList']]
                                self.addToCSV(
                                    tableName=self.replyDB, data_list=data_list, columns=reply_column)

                    self.webCrawlerRunCheck()

                    self.currentDate += self.deltaD
                    self.IntegratedDB = NaverBlogCrawler_obj.CountReturn()
                    
                    res = requests.put(f"{self.api_url}/crawls/{self.dbUid}/count", json=self.IntegratedDB, headers=self.api_headers).json()

                except Exception as e:
                    error_msg = self.error_detector()
                    error_data = self.error_dump(
                        1002, error_msg, self.currentDate_str)
                    self.ReturnChecker(error_data)
            return

    def Naver_Cafe_Crawler(self, option):

        NaverCafeCrawler_obj = NaverCafeCrawler(
            proxy_option=self.proxy_option, print_status_option=True)
        NaverCafeCrawler_obj.setCrawlSpeed(self.speed)

        self.option = option
        self.DBtype = "navercafe"
        self.DBMaker(self.DBtype)

        # initial list
        self.urlList = []

        article_column = ["NaverCafe Name", "NaverCafe MemberCount", "Article Writer", "Article Title",
                          "Article Text", "Article Date", "Article ReadCount", "Article ReplyCount", "Article URL"]
        reply_column = ["Reply Num", "Reply Writer", "Reply Date",
                        'Reply Text', 'Article URL', 'Article Day']

        self.makeCSV(tableName=self.articleDB, columns=article_column)
        if option == 2:
            self.makeCSV(tableName=self.replyDB, columns=reply_column)

        if self.weboption == 0:
            self.infoPrinter()

        while self.running == True:
            for dayCount in range(self.date_range + 1):
                try:
                    self.currentDate_str = self.currentDate.strftime('%Y%m%d')
                    percent = str(round(((dayCount+1)/self.date_range)*100, 1))
                    NaverCafeCrawler_obj.setPrintData(
                        self.currentDate.strftime('%Y.%m.%d'), percent, self.weboption)

                    # finish line
                    if dayCount == self.date_range:
                        self.FinalOperator()
                        return

                    # Cafe URL Part
                    urlList_returnData = NaverCafeCrawler_obj.urlCollector(
                        keyword=self.keyword, startDate=self.currentDate_str, endDate=self.currentDate_str)
                    if self.ReturnChecker(urlList_returnData) == False:
                        if dayCount == 0:
                            msg_text = (
                                "[ CRAWLER STOPPED ]\n\n"
                                f"초기 데이터 수집 불가로 {self.DBname} 크롤링이 중단되었습니다\n\n"
                                f"IP Proxy 프로그램이 가동 중인지, IP가 최신 버전으로 업데이트되었는지 확인바랍니다\n"
                            )
                            self.sendPushOver(
                                msg_text, user_key=self.pushoverKey)
                            self.DBinfoRecorder(False, True)
                            self.localDBRemover()
                            os._exit(1)
                        self.currentDate += self.deltaD
                        continue

                    self.urlList = urlList_returnData['urlList']

                    FullreturnData = asyncio.run(
                        NaverCafeCrawler_obj.asyncMultiCollector(self.urlList, option))

                    for returnData in FullreturnData:

                        article_returnData = returnData['articleData']
                        if self.ReturnChecker(article_returnData) == True and article_returnData['articleData'] != []:
                            self.addToCSV(tableName=self.articleDB, data_list=[
                                          article_returnData['articleData']], columns=article_column)
                        else:
                            continue

                        if option == 2:
                            replyList_returnData = returnData['replyData']
                            if self.ReturnChecker(replyList_returnData) == True and replyList_returnData['replyList'] != []:
                                data_list = [sublist + [article_returnData['articleData'][5]]
                                             for sublist in replyList_returnData['replyList']]
                                self.addToCSV(
                                    tableName=self.replyDB, data_list=data_list, columns=reply_column)

                    self.webCrawlerRunCheck()

                    self.currentDate += self.deltaD
                    self.IntegratedDB = NaverCafeCrawler_obj.CountReturn()
                    
                    res = requests.put(f"{self.api_url}/crawls/{self.dbUid}/count", json=self.IntegratedDB, headers=self.api_headers).json()

                except Exception as e:
                    error_msg = self.error_detector()
                    error_data = self.error_dump(
                        1002, error_msg, self.currentDate_str)
                    self.ReturnChecker(error_data)
            return

    def YouTube_Crawler(self, option):
        collection = self.mongoClient['crawler']['youtube_api']
        api_list = []
        # _id는 제외, "API code"만 포함
        cursor = collection.find({}, {"_id": 0, "API code": 1})

        for doc in cursor:
            if "API code" in doc:
                api_list.append(doc["API code"])

        YouTubeCrawler_obj = YouTubeCrawler(
            api_list=api_list, proxy_option=self.proxy_option, print_status_option=True)

        self.option = option
        self.DBtype = "youtube"
        self.DBMaker(self.DBtype)
        self.api_num = 1

        self.urlList = []

        article_column = ['YouTube Channel', 'Article URL', 'Article Title', 'Article Text',
                          'Article Date', 'Article ViewCount', 'Article Like', 'Article ReplyCount']
        reply_column = ['Reply Num', 'Reply Writer', 'Reply Date',
                        'Reply Text', 'Reply Like', 'Article URL', 'Article Day']
        rereply_column = ['Rereply Num', 'Rereply Writer', 'Rereply Date',
                          'Rereply Text', 'Rereply Like', 'Article URL', 'Article Day']

        self.makeCSV(tableName=self.articleDB, columns=article_column)
        self.makeCSV(tableName=self.replyDB, columns=reply_column)
        self.makeCSV(tableName=self.rereplyDB, columns=rereply_column)

        if self.weboption == 0:
            self.infoPrinter()

        while self.running == True:
            for dayCount in range(self.date_range + 1):
                try:
                    self.currentDate_str = self.currentDate.strftime('%Y%m%d')
                    percent = str(round(((dayCount+1)/self.date_range)*100, 1))
                    YouTubeCrawler_obj.setPrintData(self.currentDate.strftime(
                        '%Y.%m.%d'), percent, self.weboption, self.api_num)

                    # finish line
                    if dayCount == self.date_range:
                        self.FinalOperator()
                        return

                    # YouTube URL Part
                    urlList_returnData = YouTubeCrawler_obj.urlCollector(
                        keyword=self.keyword, startDate=self.currentDate_str, endDate=self.currentDate_str)
                    if self.ReturnChecker(urlList_returnData) == False:
                        if dayCount == 0:
                            msg_text = (
                                "[ CRAWLER STOPPED ]\n\n"
                                f"초기 데이터 수집 불가로 {self.DBname} 크롤링이 중단되었습니다\n\n g"
                                f"IP Proxy 프로그램이 가동 중인지, IP가 최신 버전으로 업데이트되었는지 확인바랍니다\n"
                            )
                            self.sendPushOver(
                                msg_text, user_key=self.pushoverKey)
                            self.DBinfoRecorder(False, True)
                            self.localDBRemover()
                            os._exit(1)
                        self.currentDate += self.deltaD
                        continue

                    self.urlList = urlList_returnData['urlList']

                    FullreturnData = YouTubeCrawler_obj.syncMultiCollector(
                        self.urlList, option)

                    for returnData in FullreturnData:

                        article_returnData = returnData['articleData']
                        if self.ReturnChecker(article_returnData) == True and article_returnData['articleData'] != []:
                            self.addToCSV(tableName=self.articleDB, data_list=[
                                          article_returnData['articleData']], columns=article_column)
                        else:
                            continue

                        replyList_returnData = returnData['replyData']
                        if self.ReturnChecker(replyList_returnData) == True:
                            if replyList_returnData['replyList'] != []:
                                data_list = [sublist + [article_returnData['articleData'][4]]
                                             for sublist in replyList_returnData['replyList']]
                                self.addToCSV(
                                    tableName=self.replyDB, data_list=data_list, columns=reply_column)
                            if replyList_returnData['rereplyList'] != []:
                                data_list = [sublist + [article_returnData['articleData'][4]]
                                             for sublist in replyList_returnData['rereplyList']]
                                self.addToCSV(
                                    tableName=self.rereplyDB, data_list=data_list, columns=rereply_column)

                    self.webCrawlerRunCheck()

                    self.currentDate += self.deltaD
                    self.IntegratedDB = YouTubeCrawler_obj.CountReturn()
                    
                    res = requests.put(f"{self.api_url}/crawls/{self.dbUid}/count", json=self.IntegratedDB, headers=self.api_headers).json()

                except Exception as e:
                    error_msg = self.error_detector()
                    error_data = self.error_dump(
                        1002, error_msg, self.currentDate_str)
                    self.ReturnChecker(error_data)
            return

    def ChinaDaily_Crawler(self, option):

        ChinaDailyCrawler_obj = ChinaDailyCrawler(
            proxy_option=self.proxy_option, print_status_option=True)

        self.option = option
        self.DBtype = "chinadaily"
        self.DBMaker(self.DBtype)

        article_column = ['Article Source', 'Article Title', 'Article Text',
                          'Article Date', 'Article Theme', 'Article URL', 'Article SearchURL']
        self.makeCSV(tableName=self.articleDB, columns=article_column)

        if self.weboption == 0:
            self.infoPrinter()

        while self.running == True:
            for dayCount in range(self.date_range + 1):
                try:
                    self.currentDate_str = self.currentDate.strftime('%Y%m%d')
                    percent = str(round(((dayCount+1)/self.date_range)*100, 1))
                    ChinaDailyCrawler_obj.setPrintData(
                        self.currentDate.strftime('%Y.%m.%d'), percent, self.weboption)

                    # finish line
                    if dayCount == self.date_range:
                        self.FinalOperator()
                        return

                    articleList_returnData = ChinaDailyCrawler_obj.articleCollector(
                        keyword=self.keyword, startDate=self.currentDate_str, endDate=self.currentDate_str)
                    if self.ReturnChecker(articleList_returnData) == False:
                        continue
                    articleList = articleList_returnData['articleList']
                    articleCnt = articleList_returnData['articleCnt']

                    if articleCnt != 0:
                        self.addToCSV(tableName=self.articleDB,
                                      data_list=articleList, columns=article_column)

                    self.webCrawlerRunCheck()

                    self.currentDate += self.deltaD
                    self.IntegratedDB = ChinaDailyCrawler_obj.CountReturn()

                except Exception as e:
                    error_msg = self.error_detector()
                    error_data = self.error_dump(
                        1002, error_msg, self.currentDate_str)
                    self.ReturnChecker(error_data)
            return

    def ChinaSina_Crawler(self, option):

        ChinaSinaCrawler_obj = ChinaSinaCrawler(
            proxy_option=self.proxy_option, print_status_option=True)
        ChinaSinaCrawler_obj.setCrawlSpeed(self.speed)

        self.option = option
        self.DBtype = "chinasina"
        self.DBMaker(self.DBtype)

        article_column = ['Article Title',
                          'Article Text', 'Article Date', 'Article URL']
        reply_column = ['Reply Num', 'Reply Writer', 'Reply Date',
                        'Reply Text', 'Reply Like', 'Article URL', 'Article Day']

        self.makeCSV(tableName=self.articleDB, columns=article_column)
        if option == 2:
            self.makeCSV(tableName=self.replyDB, columns=reply_column)

        if self.weboption == 0:
            self.infoPrinter()

        DateRangeList = ChinaSinaCrawler_obj.DateSplitter(
            self.startDate, self.endDate)
        DateRangeList.append(DateRangeList[-1])
        DateRangeCnt = 0

        while self.running == True:
            for DateRange in DateRangeList:
                try:
                    articleList = []
                    DateRangeCnt += 1
                    currentDate_start = DateRange[0]
                    currentDate_end = DateRange[1]
                    currentDate_str_start = datetime.strptime(
                        DateRange[0], '%Y%m%d').date()
                    currentDate_str_end = datetime.strptime(
                        DateRange[1], '%Y%m%d').date()
                    percent = str(
                        round(((DateRangeCnt+1)/len(DateRangeList))*100, 1))

                    ChinaSinaCrawler_obj.setPrintData(
                        f"{currentDate_str_start.strftime('%Y.%m.%d')} ~ {currentDate_str_end.strftime('%Y.%m.%d')}", percent, self.weboption)

                    if DateRangeCnt == len(DateRangeList):
                        self.FinalOperator()
                        return

                    urlList_returnData = ChinaSinaCrawler_obj.urlCollector(
                        keyword=self.keyword, startDate=currentDate_start, endDate=currentDate_end)
                    if self.ReturnChecker(urlList_returnData) == False:
                        if DateRange == DateRangeList[0]:
                            self.DBinfoRecorder(False, True)
                            self.localDBRemover()
                            os._exit(1)
                        continue
                    self.urlList = urlList_returnData['urlList']

                    FullreturnData = asyncio.run(
                        ChinaSinaCrawler_obj.asyncMultiCollector(self.urlList, option))

                    for returnData in FullreturnData:

                        article_returnData = returnData['articleData']
                        if self.ReturnChecker(article_returnData) == True and article_returnData['articleData'] != []:
                            articleList.append(
                                article_returnData['articleData'])
                        else:
                            continue

                        if option == 2:
                            replyList_returnData = returnData['replyData']
                            if self.ReturnChecker(replyList_returnData) == True and replyList_returnData['replyList'] != []:
                                data_list = [sublist + [article_returnData['articleData'][2]]
                                             for sublist in replyList_returnData['replyList']]
                                self.addToCSV(
                                    tableName=self.replyDB, data_list=data_list, columns=reply_column)

                    self.addToCSV(tableName=self.articleDB, data_list=sorted(
                        articleList, key=lambda x: datetime.strptime(x[2], "%Y-%m-%d")), columns=article_column)

                    self.webCrawlerRunCheck()
                    self.IntegratedDB = ChinaSinaCrawler_obj.CountReturn()

                except Exception as e:
                    error_msg = self.error_detector()
                    error_data = self.error_dump(
                        1002, error_msg, self.currentDate_str)
                    self.ReturnChecker(error_data)
            return


def controller():
    option_dic = {
        1: "\n1. 기사 + 댓글\n2. 기사 + 댓글/대댓글\n3. 기사\n4. 기사 + 댓글(추가정보)\n",
        2: "\n1. 블로그 본문\n2. 블로그 본문 + 댓글/대댓글\n",
        3: "\n1. 카페 본문\n2. 카페 본문 + 댓글/대댓글\n",
        4: "\n1. 영상 정보 + 댓글/대댓글 (100개 제한)\n2. 영상 정보 + 댓글/대댓글(무제한)\n",
        5: "\n1. 기사\n",
        6: "\n1. 기사\n2. 기사 + 댓글\n"
    }
    print("================ Crawler Controller ================")
    name = input("본인의 이름을 입력하세요: ")

    print("\n[ 크롤링 대상 ]\n")
    print("1. Naver News\n2. Naver Blog\n3. Naver Cafe\n4. YouTube\n5. ChinaDaily\n6. ChinaSina")

    while True:
        control_ask = int(input("\n입력: "))
        if control_ask in [1, 2, 3, 4, 5, 6]:
            break
        else:
            print("다시 입력하세요")

    startDate = input("\nStart Date (ex: 20230101): ")
    endDate = input("End Date (ex: 20231231): ")
    keyword = input("\nKeyword: ")

    print(option_dic[control_ask])

    while True:
        option = int(input("Option: "))
        if option in [1, 2, 3, 4]:
            break
        else:
            print("다시 입력하세요")

    upload = input("\n메일로 크롤링 데이터를 받으시겠습니까(1/0)? ")
    speed = input("\n속도를 입력하십시오(1~10):  ")
    weboption = 0

    Crawler_obj = Crawler(name, startDate, endDate,
                          keyword, upload, speed, weboption)
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


def manualTokenizer():
    def tokenization(data):  # 갱신 간격 추가
        kiwi = Kiwi(num_workers=-1)
        for column in data.columns.tolist():
            if 'Text' in column:
                textColumn_name = column

        text_list = list(data[textColumn_name])
        tokenized_data = []

        total_texts = len(text_list)
        total_time = 0  # 전체 소요시간을 계산하기 위한 변수

        for index, text in enumerate(text_list):
            start_time = time.time()  # 처리 시작 시간 기록
            try:
                if not isinstance(text, str):
                    tokenized_data.append([])
                    continue  # 문자열이 아니면 넘어감

                text = re.sub(r'[^가-힣a-zA-Z\s]', '', text)
                tokens = kiwi.tokenize(text)
                tokenized_text = [
                    token.form for token in tokens if token.tag in ('NNG', 'NNP')]

                # 리스트를 쉼표로 구분된 문자열로 변환
                tokenized_text_str = ", ".join(tokenized_text)
                tokenized_data.append(tokenized_text_str)
            except:
                tokenized_data.append([])

            # 처리 완료 후 시간 측정
            end_time = time.time()
            total_time += end_time - start_time

            # 평균 처리 시간 계산
            avg_time_per_text = total_time / (index + 1)
            remaining_time = avg_time_per_text * \
                (total_texts - (index + 1))  # 남은 시간 추정

            # 남은 시간을 시간과 분으로 변환
            remaining_minutes = int(remaining_time // 60)
            remaining_seconds = int(remaining_time % 60)

            update_interval = 500
            # N개마다 한 번 갱신
            if (index + 1) % update_interval == 0 or index + 1 == total_texts:
                progress_value = round((index + 1) / total_texts * 100, 2)
                print(
                    f'\r{textColumn_name.split(" ")[0]} Tokenization Progress: {progress_value}% | '
                    f'예상 남은 시간: {remaining_minutes}분 {remaining_seconds}초', end=''
                )

        data[textColumn_name] = tokenized_data
        return data

    DBpath = "/mnt/ssd/bigmaclab/crawldata/navernews_보호관찰_20200101_20250331_0526_2122"
    parquet_files = [f for f in os.listdir(DBpath) if f.endswith('.parquet')]
    for file_name in parquet_files:
        table_name = file_name.rsplit('.', 1)[0]
        file_path = os.path.join(DBpath, file_name)
        print(f"{table_name} 읽는 중...")

        data_df = pd.read_parquet(file_path)

        # Step 3: Reply 관련 테이블이면 전처리 수행
        # 전처리 부분 수정 예시
        if 'reply' in table_name or 'rereply' in table_name:
            date_column = 'Rereply Date' if 'rereply' in table_name else 'Reply Date'
            text_column = 'Rereply Text' if 'rereply' in table_name else 'Reply Text'

            data_df[date_column] = pd.to_datetime(
                data_df[date_column], errors='coerce').dt.date

            # 결측치를 빈 문자열로 치환
            data_df[text_column] = data_df[text_column].fillna('')

            grouped = data_df.groupby('Article URL')
            data_df = grouped.agg({
                text_column: lambda x: ' '.join(x),
                'Article Day': 'first'
            }).reset_index()

            data_df = data_df.rename(
                columns={'Article Day': date_column})
            data_df = data_df.sort_values(by=date_column)


        # Step 4: Tokenization
        token_df = tokenization(data_df)

        # Step 5: 저장 (선택 사항: parquet 저장 or print only)
        for col in token_df.columns:
            if token_df[col].apply(lambda x: isinstance(x, list)).any():
                token_df[col] = token_df[col].apply(lambda x: ' '.join(
                    map(str, x)) if isinstance(x, list) else x)

        token_file_path = os.path.join(
            DBpath, f"token_{table_name}.parquet")
        token_df.to_parquet(token_file_path, index=False)
        print(f"Token 저장 완료: token_{table_name}.parquet")

if __name__ == '__main__':
    controller()