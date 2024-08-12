# -*- coding: utf-8 -*-
import signal
import sys

from CRAWLER import Crawler

sys.stdout.reconfigure(encoding='utf-8')

name         = sys.argv[1]
crawl_object = int(sys.argv[2])
start        = sys.argv[3]
end          = sys.argv[4]
option       = int(sys.argv[5])
keyword      = sys.argv[6]
upload       = sys.argv[7]
weboption    = 1
speed        = 3

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

def signal_handler(sig, frame):
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

Crawler_obj = Crawler(name, start, end, keyword, int(upload), speed, weboption)
if crawl_object == 1:
    Crawler_obj.Naver_News_Crawler(option)

elif crawl_object == 2:
    Crawler_obj.Naver_Blog_Crawler(option)
    
elif crawl_object == 3:
    Crawler_obj.Naver_Cafe_Crawler(option)
    
elif crawl_object == 4:
    Crawler_obj.YouTube_Crawler(option)

elif crawl_object == 5:
    Crawler_obj.ChinaDaily_Crawler(option)
    
elif crawl_object == 6:
    Crawler_obj.ChinaSina_Crawler(option)

