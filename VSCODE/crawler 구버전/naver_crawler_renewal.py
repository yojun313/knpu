# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup
import codecs
import sys
from dbapi import *
from parsers import *


from datetime import date, timedelta
import datetime

START_DATE = "2019.07.15"
END_DATE = "2019.07.13"


# 1 = 기사만
# 2 = 기사 + 댓글
# 3 = 기사 + 댓글 + 대댓글
OPTION = "3"
press_filter = "1"


def switchKeywordToRealKeyword(keyword):
    return keyword.replace(" ", "+")


press = []

if __name__ == "__main__":
    # Log file 생성
    f = open("./log.txt", "w")
    f.close()

    print("Naver Crawler 2023.10")
    print("Start Crawling. - Naver")

    # 댓글 테스트
    # initializeDB('TEST')
    # parseURL('https://news.naver.com/main/read.nhn?mode=LSD&mid=sec&sid1=103&oid=437&aid=0000132190','enter')

    try:
        # 검색 시작 날짜를 받아서 START_DATE에 저장
        start = input("Start Date:=")
        # start = '2022.08.01'
        START_DATE = start
        # 검색 마지막 날짜를 받아서 END_DATE에 저장
        end = input("End Date:=")
        # end = '2023.07.31'
        END_DATE = end

        start = start.split(".")
        startYear = int(start[0])
        startMonth = int(start[1])
        startDay = int(start[2])

        end = end.split(".")
        endYear = int(end[0])
        endMonth = int(end[1])
        endDay = int(end[2])

        d_start = datetime.date(startYear, startMonth, startDay)
        d_end = datetime.date(endYear, endMonth, endDay)
        deltaD = timedelta(days=1)
        currentDate = d_start

        # Keyword를 받아서 'keyword' 에 저장
        keyword = input("Keyword:=")
        # keyword = '스토킹 범죄'

        print("1. 기사만 \n2. 기사 + 댓글\n3. 기사 + 댓글 + 대댓글")
        option = input("Option:=")
        # 1 = 기사만
        # 2 = 기사 + 댓글
        # 3 = 기사 + 댓글 + 대댓글

        refinedword = keyword.replace('"', "")
        refinedword = refinedword.replace(" ", "")
        print(refinedword)
        keyword = switchKeywordToRealKeyword(keyword)
        now = datetime.datetime.now()

        DBname = "Naver_" + refinedword + "_" + now.strftime("%y%m%d_%H%M%S")
        dbconn = DBConnector()
        dbconn.initialize(DBname)

        while currentDate <= d_end:
            trans_date = str(currentDate).replace("-", ".")
            print(trans_date)
            newsURLs = getURLs(keyword, trans_date, dbconn, int(option))
            currentDate += deltaD

    except Exception as e:
        _, _, tb = sys.exc_info()  # tb -> traceback object
        msg = (
            "File name: "
            + __file__
            + "\n"
            + "Error line= {}".format(tb.tb_lineno)
            + "\n"
            + "Error: {}".format(sys.exc_info()[0])
            + " "
            + str(e)
            + "\n"
            + "Date : "
            + currentDate
            + "\n"
            + "keyword : "
            + keyword
        )
        print(msg)

    print("\n\n\n크롤링 종료.\n\n\n")
