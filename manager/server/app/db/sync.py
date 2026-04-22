# cd knpu/manager/server
# python3 -m app.db.sync

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from . import client, manager_db

## --- BE CAREFUL -- ##
## Do Not Modify This Function

def sync_manager_databases():
    targets = [('manager', 'manager_dev'), ('crawler', 'crawler_dev')]
    
    for target in targets:
        src_db_name = target[0]
        target_db_name = target[1]
        
        client.drop_database(target_db_name)
        
        src_db = client[src_db_name]
        target_db = client[target_db_name]
        
        for coll_name in src_db.list_collection_names():
            src_db[coll_name].aggregate([{"$out": {"db": target_db_name, "coll": coll_name}}])
            
            indexes = src_db[coll_name].index_information()
            for index_name, index_info in indexes.items():
                if index_name == "_id_":
                    continue
                
                keys = index_info['key']
                options = {k: v for k, v in index_info.items() if k not in ['v', 'key', 'ns']}
                target_db[coll_name].create_index(keys, **options)

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
            {"_id": doc["_id"]},
            {"$set": {"datetime_kst": datetime_kst_str}}
        )
        
def set_notified_true(collection_name):
    coll = manager_db[collection_name]
    coll.update_many({}, {"$set": {"notified": True}})

if __name__ == '__main__':
    sync_manager_databases()