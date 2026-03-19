


import urllib3
from datetime import datetime, timedelta, timezone
import requests

import socket
import re
import warnings
import asyncio
import traceback
import time
import os
import sys
from config import CRAWL_PATH, CRAWL_LOG_PATH, API_URL, CRAWLCOM
from libs.req import api_headers


def makeDB(DBname, DBtype, startdate, enddate, option, keyword, requester, requesterUid):
    dbname_date = "_{}_{}".format(startdate, enddate)

    now_kst = datetime.now(timezone.utc).astimezone(
        timezone(timedelta(hours=9))
    ).strftime('%m%d_%H%M')

    DBname = f"{DBtype}_{DBname}{dbname_date}_{now_kst}"
    DBpath = os.path.join(CRAWL_PATH, DBname)

    json = {
        "name": DBname,
        "userUid": requesterUid,
        "crawlOption": option,
        "requester": requester,
        "keyword": keyword,
        "dbSize": 0,
        "crawlCom": CRAWLCOM,
        "crawlSpeed": 1,
    }

    res = requests.post(API_URL + '/crawls/add', json=json, headers=api_headers).json()
    DBuid = res['data']['uid']

    os.makedirs(DBpath)
    log = open(os.path.join(CRAWL_LOG_PATH, DBname + '_log.txt'), 'w+')

    msg = (
        f"=======================================================================================================================================\n"
        f"{'User:':<15} {requester}\n"
        f"{'Object:':<15} {DBtype}\n"
        f"{'Option:':<15} {option}\n"
        f"{'Keyword:':<15} {keyword}\n"
        f"{'Date Range:':<15} {startdate} ~ {enddate}\n"
        f"{'Crawl Start:':<15} {datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M')}\n"
        f"{'Computer:':<15} {CRAWLCOM}\n"
        f"{'DB path:':<15} {DBpath}\n"
        f"=======================================================================================================================================\n"
    )
    log.write(msg + '\n\n')
    log.close()
    
    return DBpath, DBuid

