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
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

class Crawler:
    
    def __init__(self, user, startDate, endDate, keyword, upload,  weboption):
        
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
        self.upload    = upload
        
        
        
        startDate_form = datetime.strptime(startDate, '%Y%m%d')
        endDate_form   = datetime.strptime(endDate, '%Y%m%d')
        
        
        self.currentDate = startDate_form.date()
        self.date_range  = (endDate_form.date() - startDate_form.date()).days
        
        print(self.currentDate)
        

if __name__ == '__main__':
    object = Crawler('문요준', '20230101', '20231231', '아이패드', upload=False, weboption=True)
    