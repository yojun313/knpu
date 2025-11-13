from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()



uri = os.getenv("MONGO_URI")
client = MongoClient(uri)

manager_db = client["manager"]
crawler_db = client["crawler"]

crawlList_db = crawler_db["db-list"]
crawlLog_db = crawler_db["log-list"]

user_db = manager_db["users"]
user_logs_db = manager_db["user-logs"]
user_bugs_db = manager_db["user-bugs"]
version_board_db = manager_db["version-board"]
bug_board_db = manager_db["bug-board"]
free_board_db = manager_db["free-board"]
auth_db = manager_db["auth"]

crawldata_path = os.getenv('CRAWLDATA_PATH')


from pathlib import Path


def getFolderSize(path):
    total_bytes = sum(f.stat().st_size for f in Path(path).rglob('*') if f.is_file())
    return total_bytes

def format_size(bytes_size):
    if bytes_size < 1024:  # 1KB 미만
        return f"{bytes_size} B"

    kb = bytes_size / 1024
    if kb < 1024:  # 1MB 미만
        return f"{kb:.0f} KB"

    mb = kb / 1024
    if mb < 1024:  # 1GB 미만
        return f"{mb:.0f} MB"

    gb = mb / 1024
    return f"{gb:.1f} GB"


def update_all_crawl_db_size():
    cursor = crawlList_db.find()

    updated_count = 0
    skipped = 0
    total = 0

    for crawlDb in cursor:
        total += 1
        name = crawlDb.get("name")
        uid = crawlDb.get("uid")

        if not name:
            skipped += 1
            continue

        folder_path = os.path.join(crawldata_path, name)

        if not os.path.exists(folder_path):
            print(f"[skip] Folder not found: {folder_path}")
            skipped += 1
            continue

        byte_size = getFolderSize(folder_path)

        crawlList_db.update_one(
            {"uid": uid},
            {"$set": {"dbSize": byte_size}}
        )

        print(f"[update] {name} → {byte_size} bytes")
        updated_count += 1

    print("\n==== Summary ====")
    print(f"Total docs: {total}")
    print(f"Updated: {updated_count}")
    print(f"Skipped: {skipped}")

if __name__ == "__main__":
    update_all_crawl_db_size()
