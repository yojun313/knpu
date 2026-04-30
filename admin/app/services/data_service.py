from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from app.db import user_logs_col, bug_board_col, db_list_col, users_col, user_bugs_col

def get_all_users():
    return list(users_col.find().sort("name", 1))

def get_user_mapping():
    """uid를 이름으로 매핑하는 딕셔너리 생성"""
    users = users_col.find({}, {"uid": 1, "name": 1})
    return {u["uid"]: u.get("name", "알 수 없음") for u in users}

def get_dashboard_stats(date_str=None):
    total_logs = user_logs_col.count_documents({})
    total_bugs = bug_board_col.count_documents({})
    total_user_bugs = user_bugs_col.count_documents({})
    
    today_query = {}
    if date_str:
        kst = ZoneInfo("Asia/Seoul")
        start_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=kst)
        end_dt = start_dt + timedelta(days=1)
        today_query = {"datetime": {"$gte": start_dt, "$lt": end_dt}}
    
    today_logs = user_logs_col.count_documents(today_query)
    today_user_bugs = user_bugs_col.count_documents(today_query)

    pipeline = [{"$group": {"_id": None, "total": {"$sum": "$dbSize"}}}]
    size_agg = list(db_list_col.aggregate(pipeline))
    total_size_bytes = size_agg[0]["total"] if size_agg else 0
    total_size_gb = round(total_size_bytes / (1024 ** 3), 2)

    return {
        "total_logs": total_logs,
        "today_logs": today_logs, 
        "total_bugs": total_bugs,
        "total_user_bugs": total_user_bugs,
        "today_user_bugs": today_user_bugs, 
        "total_size_gb": total_size_gb
    }

def get_admin_uids():
    admins = users_col.find({"role": "admin"}, {"uid": 1})
    return [a["uid"] for a in admins]

def build_search_query(name=None, date_str=None, user_map=None):
    query = {}
    admin_uids = get_admin_uids()
    
    if name and user_map:
        matched_uids = [uid for uid, uname in user_map.items() if name.lower() in uname.lower()]
        query["userUid"] = {"$in": matched_uids}
    else:
        query["userUid"] = {"$nin": admin_uids}
        
    if date_str:
        try:
            kst = ZoneInfo("Asia/Seoul")
            start_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=kst)
            end_dt = start_dt + timedelta(days=1)
            query["datetime"] = {"$gte": start_dt, "$lt": end_dt}
        except ValueError:
            pass
            
    return query

def get_recent_logs(limit=10, name=None, date_str=None):
    user_map = get_user_mapping()
    query = build_search_query(name, date_str, user_map)
    
    logs = list(user_logs_col.find(query).sort("datetime", -1).limit(limit))
    
    for log in logs:
        log["datetime"] = log.get("datetime_kst") or log.get("datetime").strftime("%Y-%m-%d %H:%M:%S")
        log["user_name"] = user_map.get(log.get("userUid"), log.get("userUid")[:8])
    return logs

def get_user_bugs(limit=50, name=None, date_str=None):
    user_map = get_user_mapping()
    query = build_search_query(name, date_str, user_map)
    
    bugs = list(user_bugs_col.find(query).sort("datetime", -1).limit(limit))
    
    for bug in bugs:
        bug["datetime"] = bug.get("datetime_kst") or bug.get("datetime").strftime("%Y-%m-%d %H:%M:%S")
        bug["user_name"] = user_map.get(bug.get("userUid"), bug.get("userUid")[:8])
    return bugs

def get_recent_crawlers(limit=10):
    crawlers = list(db_list_col.find().sort("startTime", -1).limit(limit))
    for c in crawlers:
        if "_id" in c:
            c["_id"] = str(c["_id"])
            
        size_bytes = c.get("dbSize", 0)
        if size_bytes > 1024 * 1024 * 1024:
            c["size_formatted"] = f"{size_bytes / (1024**3):.2f} GB"
        else:
            c["size_formatted"] = f"{size_bytes / (1024**2):.1f} MB"
            
        end_time_str = str(c.get("endTime", ""))
        if "%" in end_time_str or not end_time_str or end_time_str == "0":
            c["is_running"] = True
        else:
            c["is_running"] = False
                
    return crawlers

def get_recent_bugs(limit=10):
    """Bug Reports 페이지용 데이터 포맷팅"""
    bugs = list(bug_board_col.find().sort("datetime", -1).limit(limit))
    for bug in bugs:
        dt = bug.get("datetime")
        if isinstance(dt, datetime):
            bug["datetime"] = dt.strftime("%Y-%m-%d %H:%M:%S")
    return bugs