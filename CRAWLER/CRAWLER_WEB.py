# -*- coding: utf-8 -*-
from CRAWLER import Crawler
import sys

sys.dont_write_bytecode = True

sys.stdout.reconfigure(encoding='utf-8')

name         = sys.argv[1]
crawl_object = int(sys.argv[2])
start        = sys.argv[3]
end          = sys.argv[4]
option       = int(sys.argv[5])
keyword      = sys.argv[6]
upload       = sys.argv[7]
weboption    = 1


'''
name = "문요준"
crawl_object = 1
start = '20230101'
end = '20230110'
option = 2
keyword = "아이패드"
upload = 'n'
weboption = 1
'''

if crawl_object == 1:
    crawler = Crawler(name, start, end, keyword, upload, weboption)
    crawler.crawl_news(option)

elif crawl_object == 2:
    crawler = Crawler(name, start, end, keyword, upload, weboption)
    crawler.crawl_blog(option)
    
elif crawl_object == 3:
    crawler = Crawler(name, start, end, keyword, upload, weboption)
    crawler.crawl_youtube(option)

