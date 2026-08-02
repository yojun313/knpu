import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from app.db import (
    user_logs_col,
    bug_board_col,
    db_list_col,
    user_bugs_col,
    homepage_users_col,
    crawler_log_col,
    manager_users_col,
    identity_history_col,
)

ANONYMOUS_AUDIT_KEY = "__anonymous__"

# AuditLogMiddleware가 자동으로 남기는 action은 "METHOD /path" 형태를 그대로 쓴다
# (예: "DELETE /api/crawl/{uid}"). source="auto" 태그가 붙기 전(이번 필드 도입 이전)에
# 기록된 문서는 이 태그가 없으므로, action 값의 형태로도 자동 기록을 걸러낸다.
_HTTP_ACTION_PATTERN = re.compile(r"^(GET|POST|PUT|PATCH|DELETE) ")


def _explicit_log_filter() -> dict:
    """User Logs 탭: '확실한 액션'이 있는 의도적 기록만 — 자동 기록(source="auto" 또는
    source 필드 도입 이전의 "METHOD /path" 형태)과 액션이 아예 없는 레거시 기록은 제외."""
    return {
        "action": {"$exists": True, "$not": _HTTP_ACTION_PATTERN},
        "source": {"$ne": "auto"},
    }


def get_all_users():
    return list(homepage_users_col.find().sort("name", 1))


def get_pending_users():
    return list(
        homepage_users_col.find({"status": "pending_approval"}).sort("created_at", 1)
    )


def _sync_identity_history():
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


def build_search_query(name=None, date_str=None, user_map=None, only_explicit=False):
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

    if only_explicit:
        query.update(_explicit_log_filter())

    return query


def _decorate_log(log: dict, user_map: dict) -> dict:
    log["datetime"] = log.get("datetime_kst") or log.get("datetime").strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    uid = log.get("userUid")
    if uid:
        log["user_name"] = user_map.get(uid, uid[:8])
    else:
        log["user_name"] = "익명 (로그인 전 요청)"
    log["action"] = log.get("action")
    log["service"] = log.get("service")
    log["outcome"] = log.get("outcome")
    req = log.get("request") or {}
    log["method"] = req.get("method")
    log["path"] = req.get("path")
    log["status_code"] = req.get("status_code")
    log["duration_ms"] = req.get("duration_ms")
    log["success"] = log.get("outcome") != "failure"
    return log


def get_recent_logs(limit=10, name=None, date_str=None):
    user_map = get_user_mapping()
    query = build_search_query(name, date_str, user_map, only_explicit=True)

    logs = list(user_logs_col.find(query).sort("datetime", -1).limit(limit))
    return [_decorate_log(log, user_map) for log in logs]


def get_users_with_log_counts():
    user_map = get_user_mapping()
    pipeline = [
        {"$match": _explicit_log_filter()},
        {"$group": {"_id": "$userUid", "count": {"$sum": 1}}},
    ]
    counts = {c["_id"]: c["count"] for c in user_logs_col.aggregate(pipeline)}
    users = []
    for uid, count in counts.items():
        if uid:
            users.append(
                {"uid": uid, "name": user_map.get(uid, uid[:8]), "count": count}
            )
        else:
            users.append(
                {
                    "uid": ANONYMOUS_AUDIT_KEY,
                    "name": "익명 (로그인 전 요청)",
                    "count": count,
                }
            )
    users.sort(key=lambda u: u["count"], reverse=True)
    return users


def get_logs_for_user(user_uid: str, page=1, per_page=30):
    user_map = get_user_mapping()
    query = {
        "userUid": None if user_uid == ANONYMOUS_AUDIT_KEY else user_uid,
        **_explicit_log_filter(),
    }
    total = user_logs_col.count_documents(query)
    skip = max(0, (page - 1) * per_page)
    logs = list(
        user_logs_col.find(query).sort("datetime", -1).skip(skip).limit(per_page)
    )
    return [_decorate_log(log, user_map) for log in logs], total


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
    return sorted(user_logs_col.distinct("service"))


def get_audit_logs(
    page=1, per_page=30, service=None, name=None, method=None, date_str=None
):
    """Audit Logs 탭: source(explicit/auto)나 action 유무와 무관하게 전부 보여준다."""
    user_map = get_user_mapping()
    query = {}

    if service:
        query["service"] = service
    if method:
        query["request.method"] = method
    if name:
        matched_uids = [
            uid for uid, uname in user_map.items() if name.lower() in uname.lower()
        ]
        query["userUid"] = {"$in": matched_uids}
    if date_str:
        try:
            kst = ZoneInfo("Asia/Seoul")
            start_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=kst)
            end_dt = start_dt + timedelta(days=1)
            query["datetime"] = {"$gte": start_dt, "$lt": end_dt}
        except ValueError:
            pass

    total = user_logs_col.count_documents(query)
    skip = max(0, (page - 1) * per_page)
    logs = list(
        user_logs_col.find(query).sort("datetime", -1).skip(skip).limit(per_page)
    )
    return [_decorate_log(log, user_map) for log in logs], total


def get_users_with_audit_counts():
    user_map = get_user_mapping()
    pipeline = [
        {"$sort": {"datetime": -1}},
        {"$group": {"_id": "$userUid", "count": {"$sum": 1}}},
    ]
    users = []
    anon_count = 0
    for r in user_logs_col.aggregate(pipeline):
        uid = r["_id"]
        if not uid:
            anon_count += r["count"]
            continue
        users.append(
            {"uid": uid, "name": user_map.get(uid, uid[:8]), "count": r["count"]}
        )

    users.sort(key=lambda u: u["count"], reverse=True)
    if anon_count:
        users.append(
            {
                "uid": ANONYMOUS_AUDIT_KEY,
                "name": "익명 (로그인 전 요청)",
                "count": anon_count,
            }
        )
    return users


def get_audit_logs_for_user(user_uid: str, page=1, per_page=30):
    user_map = get_user_mapping()
    query = {"userUid": None if user_uid == ANONYMOUS_AUDIT_KEY else user_uid}
    total = user_logs_col.count_documents(query)
    skip = max(0, (page - 1) * per_page)
    logs = list(
        user_logs_col.find(query).sort("datetime", -1).skip(skip).limit(per_page)
    )
    return [_decorate_log(log, user_map) for log in logs], total


def get_crawler_logs(uid: str):
    doc = crawler_log_col.find_one({"uid": uid})
    return doc.get("logs", []) if doc else []


def get_recent_bugs(limit=10):
    bugs = list(bug_board_col.find().sort("datetime", -1).limit(limit))
    for bug in bugs:
        dt = bug.get("datetime")
        if isinstance(dt, datetime):
            bug["datetime"] = dt.strftime("%Y-%m-%d %H:%M:%S")
    return bugs


def get_users_with_bug_report_counts():
    user_map = get_user_mapping()
    pipeline = [{"$group": {"_id": "$writerUid", "count": {"$sum": 1}}}]
    counts = {
        c["_id"]: c["count"] for c in bug_board_col.aggregate(pipeline) if c["_id"]
    }
    users = [
        {"uid": uid, "name": user_map.get(uid, uid[:8]), "count": count}
        for uid, count in counts.items()
    ]
    users.sort(key=lambda u: u["count"], reverse=True)
    return users


def get_bug_reports_for_user(writer_uid: str, page=1, per_page=30):
    query = {"writerUid": writer_uid}
    total = bug_board_col.count_documents(query)
    skip = max(0, (page - 1) * per_page)
    bugs = list(
        bug_board_col.find(query).sort("datetime", -1).skip(skip).limit(per_page)
    )
    for bug in bugs:
        dt = bug.get("datetime")
        if isinstance(dt, datetime):
            bug["datetime"] = dt.strftime("%Y-%m-%d %H:%M:%S")
    return bugs, total


def get_users_with_user_bug_counts():
    user_map = get_user_mapping()
    pipeline = [{"$group": {"_id": "$userUid", "count": {"$sum": 1}}}]
    counts = {
        c["_id"]: c["count"] for c in user_bugs_col.aggregate(pipeline) if c["_id"]
    }
    users = [
        {"uid": uid, "name": user_map.get(uid, uid[:8]), "count": count}
        for uid, count in counts.items()
    ]
    users.sort(key=lambda u: u["count"], reverse=True)
    return users


def get_user_bugs_for_user(user_uid: str, page=1, per_page=30):
    user_map = get_user_mapping()
    query = {"userUid": user_uid}
    total = user_bugs_col.count_documents(query)
    skip = max(0, (page - 1) * per_page)
    bugs = list(
        user_bugs_col.find(query).sort("datetime", -1).skip(skip).limit(per_page)
    )
    for bug in bugs:
        bug["datetime"] = bug.get("datetime_kst") or bug.get("datetime").strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        bug["user_name"] = user_map.get(bug.get("userUid"), bug.get("userUid")[:8])
    return bugs, total
