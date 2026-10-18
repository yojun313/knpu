# cd knpu/manager/server
# python3 -m app.db.sync

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from . import client, manager_db


def migrate_kst(collection_name):
    coll = manager_db[collection_name]
    kst = ZoneInfo("Asia/Seoul")

    all_docs = coll.find()

    for doc in all_docs:
        dt = doc.get("datetime")
        if not dt or not isinstance(dt, datetime):
            continue

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        dt_kst = dt.astimezone(kst)
        datetime_kst_str = dt_kst.strftime("%Y-%m-%d %H:%M:%S")

        coll.update_one(
            {"_id": doc["_id"]}, {"$set": {"datetime_kst": datetime_kst_str}}
        )


def set_notified_true(collection_name):
    coll = manager_db[collection_name]
    coll.update_many({}, {"$set": {"notified": True}})
