from CrawlerPackage.NaverCrawlerPackage.NaverNewsCrawler_Package  import NaverNewsCrawler
from CrawlerPackage.NaverCrawlerPackage.NaverBlogCrawler_Package  import NaverBlogCrawler
from CrawlerPackage.NaverCrawlerPackage.NaverCafeCrawler_Package  import NaverCafeCrawler
from CrawlerPackage.OtherCrawlerPackage.YouTubeCrawler_Package    import YouTubeCrawler
from CrawlerPackage.ChinaCrawlerPackage.ChinaDailyCrawler_Package import ChinaDailyCrawler

from CrawlerPackage.GooglePackage import GooglePackage
from CrawlerPackage.ToolPackage   import ToolPackage

import urllib3
import warnings
import socket
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

class Crawler:
    
    def __init__(self, user, startDate, endDate, keyword, upload,  weboption):
        if socket.gethostname() == "DESKTOP-502IMU5" or socket.gethostname() == "DESKTOP-0I9OM9K":
            self.crawler_folder_path = 'C:/Users/User/Desktop/BIGMACLAB/CRAWLER'
            self.scrapdata_path      = os.path.join(self.crawler_folder_path, 'scrapdata')
            self.token_path          = self.crawler_folder_path
            
        elif socket.gethostname() == "Yojuns-MacBook-Pro.local":
            self.crawler_folder_path = '/Users/yojunsmacbookprp/Documents/BIGMACLAB/CRAWLER'
            self.scrapdata_path      = os.path.join(self.crawler_folder_path, 'scrapdata')
            self.token_path          = self.crawler_folder_path
            
        self.user = user
        
        