from Package.NaverCrawlerPackage.NaverNewsCrawler_Package  import NaverNewsCrawler
from Package.NaverCrawlerPackage.NaverBlogCrawler_Package  import NaverBlogCrawler
from Package.NaverCrawlerPackage.NaverCafeCrawler_Package  import NaverCafeCrawler
from Package.OtherCrawlerPackage.YouTubeCrawler_Package    import YouTubeCrawler
from Package.ChinaCrawlerPackage.ChinaDailyCrawler_Package import ChinaDailyCrawler

from Package.GooglePackage import GooglePackage
from Package.ToolPackage   import ToolPackage

from datetime import datetime
import urllib3
import warnings
import socket
import os
import sys
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

class Crawler:
    
    def __init__(self, user, startDate, endDate, keyword, upload, weboption):
        
        self.ToolPackage_obj   = ToolPackage()
        self.GooglePackage_obj = GooglePackage(self.ToolPackage_obj.pathFinder()['token_path'])
        
        # Computer Info
        self.scrapdata_path = self.ToolPackage_obj.pathFinder()['scrapdata_path']
        self.crawlcom       = self.ToolPackage_obj.pathFinder()['computer_name']
        
        # User Info
        self.user      = user
        self.userEmail = self.ToolPackage_obj.get_userEmail(user)
        
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

    def DBMaker(self, DBtype):
        dbname_date = "_{}_{}".format(self.startDate, self.endDate)
        self.DBname      = DBtype + '_' + self.DBkeyword + dbname_date + "_" + self.now.strftime('%m%d_%H%M')
        self.DBpath      = os.path.join(self.scrapdata_path, self.DBname)
        
        try:
            os.mkdir(self.DBpath)
            log = open(os.path.join(self.DBpath, self.DBname + '_log.txt'),'w+')
            
            msg = (
                f"====================================================================================================================\n"
                f"{'User:':<15} {self.user}\n"
                f"{'Object:':<15} {self.DBtype}\n"
                f"{'Option:':<15} {self.option}\n"
                f"{'Keyword:':<15} {self.keyword}\n"
                f"{'Date Range:':<15} {self.startDate_form.strftime('%Y.%m.%d')} ~ {self.startDate_form.strftime('%Y.%m.%d')}\n"
                f"{'Computer:':<15} {self.crawlcom}\n"
                f"{'DB path:':<15} {self.DBpath}\n"
                f"{'Drive Upload:':<15} {self.upload}\n"
                f"====================================================================================================================\n\n\n\n"
            )
            log.write(msg)
            log.close()
        except:
            print("Error: 폴더 생성 실패")
            sys.exit()
    
    def infoPrinter(self):
        print("====================================================================================================================") 
        print(f"{'User:':<15} {self.user}")
        print(f"{'Object:':<15} {self.DBtype}")
        print(f"{'Option:':<15} {self.option}")
        print(f"{'Keyword:':<15} {self.keyword}")
        print(f"{'Date Range:':<15} {self.startDate_form.strftime('%Y.%m.%d')} ~ {self.startDate_form.strftime('%Y.%m.%d')}")
        print(f"{'Computer:':<15} {self.crawlcom}")
        print(f"{'DB path:':<15} {self.DBpath}")
        print(f"{'Drive Upload:':<15} {self.upload}")
        print("====================================================================================================================\n")
      
    def ReturnChecker(self, value):
        error = False
        if isinstance(value, int) == True:
            err_msg_title = self.ToolPackage_obj.error_extractor(value)
            err_msg_content = ""
            error = True
            
        elif isinstance(value, dict) == True:
            first_key = list(value.keys())[0]
            if first_key == 'Error Code':
                err_msg_title = self.ToolPackage_obj.error_extractor(value['Error Code'])
                err_msg_content = value['Error Msg']
                err_target = value['Error Target']
                error = True
        
        if error == True:
            log = open(os.path.join(self.DBpath, self.DBname + '_log.txt'),'a')
            
            
            
            msg = (
                f"Error Time: {self.now}\n"
                f"Error Type: {err_msg_title}\n"
                f"Error Detail: {err_msg_content}\n"
                f"Error Target: {err_target}\n\n\n"
            )
            log.write(msg)
            log.close()
            return True
        else:
            return False
            
    def NaverNewsCrawler(self, option):
        
        NaverNewsCrawler_obj = NaverNewsCrawler(True)
        
        self.option = option
        self.DBtype = "Naver_News"
        self.DBMaker(self.DBtype)
        
        self.article_list    = [["NaverNews Press", "NaverNews Type", "NaverNews URL", "NaverNews Title", "NaverNews Text", "NaverNews Date", "NaverNews ReplyCnt"]]
        self.statistics_list = [["NaverNews Press", "NaverNews Type", "NaverNews URL", "NaverNews Title", "NaverNews Text", "NaverNews Date", "NaverNews ReplyCnt", "male(%)", "female(%)", "10Y(%)", "20Y(%)", "30Y(%)", "40Y(%)", "50Y(%)", "60Y(%)"]]
        self.reply_list      = [["Reply Num", "Reply Writer", "Reply Date", "Reply Text", "Rereply Count", "Reply Like", "Reply Bad", "Reply LikeRatio", 'Reply Sentiment', 'NaverNews URL', 'Reply ID']]
        self.rereply_list    = [["Reply_ID", "Rereply Writer", "Rereply Date", "Rereply Text", "Rereply Like", "Rereply Bad", "Rereply LikeRatio", 'Rereply Sentiment' 'NaverNews URL']]
        
        if self.weboption == 0:
            self.infoPrinter()
        
        for i in range(self.date_range):
            self.progress = i
            currentDate_str = self.currentDate.strptime('%Y%m%d')
            returnData = NaverNewsCrawler_obj.urlCollector(keyword=self.keyword, startDate=currentDate_str, endDate=currentDate_str)
            
            if self.ReturnChecker(returnData) == True:
                continue
            
            self
            
        
        
    
    
if __name__ == '__main__':
    object = Crawler('문요준', '20230101', '20231231', '아이패드', upload=False, weboption=True)
    object.NaverNewsCrawler(1)