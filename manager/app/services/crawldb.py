from core.setting import get_setting
from services.api import Request

def updateDB(parent):
    sort_by = 'starttime' if get_setting('DBKeywordSort') == 'default' else 'keyword'
    mine = 1 if get_setting('MyDB') != 'default' else 0

    res = Request(
        'get', f'/crawls/list?sort_by={sort_by}&mine={mine}').json()
    
    parent.db_list = res['data']
    parent.fullStorage = res['fullStorage']
    parent.activeCrawl = res['activeCrawl']

    currentDB = {
        'DBuids': [db['uid'] for db in parent.db_list],
        'DBnames': [db['name'] for db in parent.db_list],
        'DBdata': parent.db_list,
        'DBtable': [(db['crawlType'], "KNPU", db['startDate'], db['endDate'], db['crawlOption'], db['status'], "KNPU", db['dbSize']) for db in parent.db_list]
    }

    return currentDB
