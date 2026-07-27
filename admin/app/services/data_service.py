from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from app.db import (
    user_logs_col,
    bug_board_col,
    db_list_col,
    user_bugs_col,
    homepage_users_col,
    audit_logs_col,
    crawler_log_col,
    manager_users_col,
    identity_history_col,
)


def get_all_users():
    return list(homepage_users_col.find().sort("name", 1))


def get_pending_users():
    return list(
        homepage_users_col.find({"status": "pending_approval"}).sort("created_at", 1)
    )


def _sync_identity_history():
    """알고 있는 모든 uid→이름을 identity_history_col에 영구 보관한다.

    매니저 데스크톱 앱이 예전에 쓰던 레거시 계정(manager.users)과 현재 중앙 로그인
    계정(homepage.users) 양쪽에서 본 적 있는 uid는 전부 여기 쌓이고, 한 번 기록되면
    계정이 삭제되거나 재가입으로 uid가 바뀌어도 지워지지 않는다 — 그래야 과거
    user-logs/user-bugs/audit-logs의 userUid가 계속 이름으로 표시된다."""
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    seen = list(homepage_users_col.find({}, {"uid": 1, "name": 1, "role": 1})) + list(
        manager_users_col.find({}, {"uid": 1, "name": 1, "role": 1})
    )
    for u in seen:
        if not u.get("uid") or not u.get("name"):
            continue
        identity_history_col.update_one(
            {"uid": u["uid"]},
            {
                "$set": {"name": u["name"], "role": u.get("role"), "last_seen": now},
                "$setOnInsert": {"first_seen": now},
            },
            upsert=True,
        )


def get_user_mapping():
    """uid를 이름으로 매핑하는 딕셔너리 생성.

    현재 계정(homepage.users)이 최우선이고, 거기 없는 uid는 지금까지 한 번이라도
    본 적 있는 모든 계정(identity_history_col — 레거시 manager.users 포함)에서
    찾아 이름을 이어서 보여준다."""
    _sync_identity_history()

    mapping = {
        d["uid"]: d.get("name", "알 수 없음")
        for d in identity_history_col.find({}, {"uid": 1, "name": 1})
    }
    for u in homepage_users_col.find({}, {"uid": 1, "name": 1}):
        mapping[u["uid"]] = u.get("name", "알 수 없음")
    return mapping


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
    total_size_gb = round(total_size_bytes / (1024**3), 2)

    return {
        "total_logs": total_logs,
        "today_logs": today_logs,
        "total_bugs": total_bugs,
        "total_user_bugs": total_user_bugs,
        "today_user_bugs": today_user_bugs,
        "total_size_gb": total_size_gb,
    }


def get_admin_uids():
    admins = homepage_users_col.find({"role": "admin"}, {"uid": 1})
    return [a["uid"] for a in admins]


def build_search_query(name=None, date_str=None, user_map=None):
    query = {}
    admin_uids = get_admin_uids()

    if name and user_map:
        matched_uids = [
            uid for uid, uname in user_map.items() if name.lower() in uname.lower()
        ]
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
        log["datetime"] = log.get("datetime_kst") or log.get("datetime").strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        log["user_name"] = user_map.get(log.get("userUid"), log.get("userUid")[:8])
    return logs


def get_users_with_log_counts():
    """User Logs 탭의 유저별 서브탭 목록 (로그 있는 유저만, 건수 많은 순)"""
    user_map = get_user_mapping()
    pipeline = [{"$group": {"_id": "$userUid", "count": {"$sum": 1}}}]
    counts = {c["_id"]: c["count"] for c in user_logs_col.aggregate(pipeline)}
    users = [
        {"uid": uid, "name": user_map.get(uid, uid[:8]), "count": count}
        for uid, count in counts.items()
    ]
    users.sort(key=lambda u: u["count"], reverse=True)
    return users


def get_logs_for_user(user_uid: str, page=1, per_page=30):
    """특정 유저의 전체 기간 로그를 페이지네이션해서 조회한다."""
    user_map = get_user_mapping()
    query = {"userUid": user_uid}
    total = user_logs_col.count_documents(query)
    skip = max(0, (page - 1) * per_page)
    logs = list(
        user_logs_col.find(query).sort("datetime", -1).skip(skip).limit(per_page)
    )
    for log in logs:
        log["datetime"] = log.get("datetime_kst") or log.get("datetime").strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        log["user_name"] = user_map.get(log.get("userUid"), log.get("userUid")[:8])
    return logs, total


def get_user_bug_by_uid(uid: str):
    return user_bugs_col.find_one({"uid": uid})


def get_user_bugs(limit=50, name=None, date_str=None):
    user_map = get_user_mapping()
    query = build_search_query(name, date_str, user_map)

    bugs = list(user_bugs_col.find(query).sort("datetime", -1).limit(limit))

    for bug in bugs:
        bug["datetime"] = bug.get("datetime_kst") or bug.get("datetime").strftime(
            "%Y-%m-%d %H:%M:%S"
        )
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

        c["is_running"] = c.get("status") == "running"

    return crawlers


def get_audit_services():
    """audit.logs에 실제로 존재하는 service 값 목록 (필터 드롭다운용)"""
    return sorted(audit_logs_col.distinct("service"))


def get_audit_logs(
    page=1, per_page=30, service=None, name=None, method=None, date_str=None
):
    """서버가 자동으로 기록한 구조화 감사 로그 조회 (변경 요청만 기록됨).
    반환: (logs, total_count)"""
    query = {}

    if service:
        query["service"] = service
    if method:
        query["method"] = method
    if name:
        query["user_name"] = {"$regex": name, "$options": "i"}
    if date_str:
        try:
            kst = ZoneInfo("Asia/Seoul")
            start_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=kst)
            end_dt = start_dt + timedelta(days=1)
            query["ts"] = {"$gte": start_dt, "$lt": end_dt}
        except ValueError:
            pass

    total = audit_logs_col.count_documents(query)
    skip = max(0, (page - 1) * per_page)
    logs = list(audit_logs_col.find(query).sort("ts", -1).skip(skip).limit(per_page))
    for log in logs:
        log["_id"] = str(log["_id"])
    return logs, total


def get_crawler_logs(uid: str):
    """crawler.log-list에서 특정 크롤링 작업(db-list.uid)의 로그를 조회한다."""
    doc = crawler_log_col.find_one({"uid": uid})
    return doc.get("logs", []) if doc else []


def get_recent_bugs(limit=10):
    """Bug Reports 페이지용 데이터 포맷팅"""
    bugs = list(bug_board_col.find().sort("datetime", -1).limit(limit))
    for bug in bugs:
        dt = bug.get("datetime")
        if isinstance(dt, datetime):
            bug["datetime"] = dt.strftime("%Y-%m-%d %H:%M:%S")
    return bugs
