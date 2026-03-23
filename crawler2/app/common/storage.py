from datetime import datetime, timedelta, timezone
import requests
import time
import os
from config import CRAWL_DATA_PATH, CRAWL_LOG_PATH, API_URL, CRAWLCOM
from common.req import api_headers


def makeDB(DBname, DBtype, startdate, enddate, option, keyword, requester, requesterUid):
    DBpath = os.path.join(CRAWL_DATA_PATH, DBname)

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

