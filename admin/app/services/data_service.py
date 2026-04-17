from datetime import datetime, timedelta
from app.db import user_logs_col, bug_board_col, db_list_col, users_col, user_bugs_col

def get_user_mapping():
    """uid를 이름으로 매핑하는 딕셔너리 생성"""
    users = users_col.find({}, {"uid": 1, "name": 1})
    return {u["uid"]: u.get("name", "알 수 없음") for u in users}

def get_dashboard_stats():
    total_logs = user_logs_col.count_documents({})
    total_bugs = bug_board_col.count_documents({})
    total_crawls = db_list_col.count_documents({})
    total_user_bugs = user_bugs_col.count_documents({}) # user-bugs 통계 추가
    
    pipeline = [{"$group": {"_id": "$dbSize"}}, {"$group": {"_id": None, "total": {"$sum": "$_id"}}}]
    size_agg = list(db_list_col.aggregate(pipeline))
    total_size_bytes = size_agg[0]["total"] if size_agg else 0
    total_size_gb = round(total_size_bytes / (1024 ** 3), 2)

    return {
        "total_logs": total_logs,
        "total_bugs": total_bugs,
        "total_crawls": total_crawls,
        "total_user_bugs": total_user_bugs,
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
        query["uid"] = {"$in": matched_uids}
    else:
        query["uid"] = {"$nin": admin_uids}
        
    if date_str:
        try:
            start_date = datetime.strptime(date_str, "%Y-%m-%d")
            end_date = start_date + timedelta(days=1)
            query["datetime"] = {"$gte": start_date, "$lt": end_date}
        except ValueError:
            pass
            
    return query

def get_recent_logs(limit=10, name=None, date_str=None):
    user_map = get_user_mapping()
    query = build_search_query(name, date_str, user_map)
    
    logs = list(user_logs_col.find(query).sort("datetime", -1).limit(limit))
    
    for log in logs:
        log["user_name"] = user_map.get(log.get("uid"), log.get("uid")[:8])
    return logs

def get_user_bugs(limit=50, name=None, date_str=None):
    """새로 추가된 user-bugs 데이터를 가져오는 함수"""
    user_map = get_user_mapping()
    query = build_search_query(name, date_str, user_map)
    
    bugs = list(user_bugs_col.find(query).sort("datetime", -1).limit(limit))
    
    for bug in bugs:
        bug["user_name"] = user_map.get(bug.get("uid"), bug.get("uid")[:8])
    return bugs

def get_recent_crawlers(limit=10):
    crawlers = list(db_list_col.find().sort("startTime", -1).limit(limit))
    for c in crawlers:
        size_mb = c.get("dbSize", 0) / (1024 * 1024)
        c["size_formatted"] = f"{size_mb:.1f} MB"
    return crawlers

def get_recent_bugs(limit=10):
    bugs = list(bug_board_col.find().sort("datetime", -1).limit(limit))
    return bugs